"""RepoProvider conformance suite — fixtures/mocks for every adapter."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest

from app.providers.azure_devops import AzureDevOpsProvider
from app.providers.base import CommitStatusInfo
from app.providers.bitbucket import BitbucketProvider
from app.providers.factory import KNOWN_PROVIDERS, get_repo_provider
from app.providers.fixture import FixtureProvider
from app.providers.generic_git import GenericGitProvider
from app.providers.gitea import GiteaProvider
from app.providers.github import GitHubProvider
from app.providers.gitlab import GitLabProvider
from app.providers.upload import UploadProvider

SAMPLE_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SAMPLE_SHA2 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _zip_sample(root: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path in root.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(root)))
    return buf.getvalue()


@pytest.mark.asyncio
async def test_known_providers_registered() -> None:
    assert "bitbucket" in KNOWN_PROVIDERS
    assert "azure_devops" in KNOWN_PROVIDERS
    assert "gitea" in KNOWN_PROVIDERS
    assert "generic_git" in KNOWN_PROVIDERS
    assert "upload" in KNOWN_PROVIDERS


@pytest.mark.asyncio
async def test_fixture_conformance(tmp_path: Path) -> None:
    provider = FixtureProvider()
    await provider.authenticate()
    repos = await provider.list_repos()
    assert repos
    refs = await provider.list_refs(repos[0].full_name)
    assert refs
    sha = await provider.resolve_ref(repos[0].full_name, refs[0].name)
    clone = await provider.shallow_clone(repos[0].full_name, refs[0].name, tmp_path / "c")
    assert clone.commit_sha == sha
    assert provider.supports_docs_as_code()
    pr = await provider.create_docs_pull_request(
        repos[0].full_name,
        head_branch="docs",
        base_branch="main",
        title="t",
        body="b",
    )
    assert pr.number == 1
    await provider.comment_on_pull_request(repos[0].full_name, 1, "hi")
    await provider.set_commit_status(
        repos[0].full_name, sha, CommitStatusInfo("docforge", "success", "ok")
    )


def _github_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/user"):
        return httpx.Response(200, json={"login": "u"})
    if path.endswith("/user/repos"):
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "full_name": "acme/app",
                    "clone_url": "https://github.com/acme/app.git",
                    "default_branch": "main",
                    "private": False,
                }
            ],
        )
    if "/branches" in path:
        return httpx.Response(
            200, json=[{"name": "main", "commit": {"sha": SAMPLE_SHA}}]
        )
    if "/tags" in path:
        return httpx.Response(200, json=[])
    if "/commits/" in path:
        return httpx.Response(200, json={"sha": SAMPLE_SHA})
    if path.endswith("/pulls") and request.method == "POST":
        return httpx.Response(
            201,
            json={
                "id": 9,
                "number": 3,
                "html_url": "https://github.com/acme/app/pull/3",
                "title": "docs",
                "state": "open",
                "head": {"sha": SAMPLE_SHA},
            },
        )
    if "/issues/" in path and path.endswith("/comments"):
        return httpx.Response(201, json={"id": 1, "body": "ok"})
    if "/statuses/" in path:
        return httpx.Response(201, json={"state": "success"})
    return httpx.Response(404, json={"message": path})


@pytest.mark.asyncio
async def test_github_conformance_mock() -> None:
    transport = httpx.MockTransport(_github_handler)
    async with httpx.AsyncClient(transport=transport, headers={}) as client:
        provider = GitHubProvider(token="t", client=client)
        await provider.authenticate()
        repos = await provider.list_repos()
        assert repos[0].full_name == "acme/app"
        refs = await provider.list_refs("acme/app")
        assert refs[0].sha == SAMPLE_SHA
        sha = await provider.resolve_ref("acme/app", "main")
        assert sha == SAMPLE_SHA
        pr = await provider.create_docs_pull_request(
            "acme/app", head_branch="docs", base_branch="main", title="t", body="b"
        )
        assert pr.number == 3
        await provider.comment_on_pull_request("acme/app", 3, "c")
        await provider.set_commit_status(
            "acme/app", sha, CommitStatusInfo("docforge", "success", "ok")
        )


def _gitlab_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/user"):
        return httpx.Response(200, json={"username": "u"})
    if path.endswith("/projects"):
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "path_with_namespace": "acme/app",
                    "http_url_to_repo": "https://gitlab.com/acme/app.git",
                    "default_branch": "main",
                    "visibility": "private",
                }
            ],
        )
    if path.endswith("/repository/branches"):
        return httpx.Response(
            200, json=[{"name": "main", "commit": {"id": SAMPLE_SHA}}]
        )
    if path.endswith("/repository/tags"):
        return httpx.Response(200, json=[])
    if "/repository/commits/" in path:
        return httpx.Response(200, json={"id": SAMPLE_SHA})
    if path.endswith("/merge_requests") and request.method == "POST":
        return httpx.Response(
            201,
            json={
                "id": 1,
                "iid": 7,
                "web_url": "https://gitlab.com/acme/app/-/merge_requests/7",
                "title": "docs",
                "state": "opened",
                "sha": SAMPLE_SHA,
            },
        )
    if "/notes" in path:
        return httpx.Response(201, json={"id": 1, "body": "ok"})
    if "/statuses/" in path:
        return httpx.Response(201, json={"status": "success"})
    return httpx.Response(404, json={"message": path})


@pytest.mark.asyncio
async def test_gitlab_conformance_mock() -> None:
    transport = httpx.MockTransport(_gitlab_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GitLabProvider(token="t", client=client)
        await provider.authenticate()
        repos = await provider.list_repos()
        assert repos[0].full_name == "acme/app"
        sha = await provider.resolve_ref("acme/app", "main")
        assert sha == SAMPLE_SHA
        pr = await provider.create_docs_pull_request(
            "acme/app", head_branch="docs", base_branch="main", title="t", body="b"
        )
        assert pr.number == 7


def _bitbucket_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/user"):
        return httpx.Response(200, json={"username": "u"})
    if "/repositories" in path and "/refs/" not in path and "/commit/" not in path:
        return httpx.Response(
            200,
            json={
                "values": [
                    {
                        "uuid": "{1}",
                        "full_name": "acme/app",
                        "is_private": True,
                        "mainbranch": {"name": "main"},
                        "links": {
                            "clone": [
                                {
                                    "name": "https",
                                    "href": "https://bitbucket.org/acme/app.git",
                                }
                            ]
                        },
                    }
                ]
            },
        )
    if "/refs/branches" in path:
        return httpx.Response(
            200,
            json={"values": [{"name": "main", "target": {"hash": SAMPLE_SHA}}]},
        )
    if "/refs/tags" in path:
        return httpx.Response(200, json={"values": []})
    if "/commit/" in path:
        return httpx.Response(200, json={"hash": SAMPLE_SHA})
    return httpx.Response(404, json={"error": path})


@pytest.mark.asyncio
async def test_bitbucket_conformance_mock() -> None:
    transport = httpx.MockTransport(_bitbucket_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = BitbucketProvider(token="t", client=client)
        await provider.authenticate()
        repos = await provider.list_repos()
        assert repos[0].full_name == "acme/app"
        refs = await provider.list_refs("acme/app")
        assert refs[0].sha == SAMPLE_SHA
        assert await provider.resolve_ref("acme/app", "main") == SAMPLE_SHA


def _ado_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/_apis/projects"):
        return httpx.Response(200, json={"value": [{"name": "proj"}]})
    if path.endswith("/_apis/git/repositories"):
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "r1",
                        "name": "app",
                        "remoteUrl": "https://dev.azure.com/org/proj/_git/app",
                        "defaultBranch": "refs/heads/main",
                        "project": {"name": "proj"},
                    }
                ]
            },
        )
    if path.endswith("/refs"):
        return httpx.Response(
            200,
            json={
                "value": [
                    {"name": "refs/heads/main", "objectId": SAMPLE_SHA},
                    {"name": "refs/tags/v1", "objectId": SAMPLE_SHA2},
                ]
            },
        )
    if path.endswith("/commits"):
        return httpx.Response(200, json={"value": [{"commitId": SAMPLE_SHA}]})
    return httpx.Response(404, json={"message": path})


@pytest.mark.asyncio
async def test_azure_devops_conformance_mock() -> None:
    transport = httpx.MockTransport(_ado_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = AzureDevOpsProvider(
            token="t", organization="org", project="proj", client=client
        )
        await provider.authenticate()
        repos = await provider.list_repos()
        assert repos[0].full_name == "proj/app"
        refs = await provider.list_refs("proj/app")
        assert any(r.name == "main" for r in refs)
        assert await provider.resolve_ref("proj/app", "main") == SAMPLE_SHA


def _gitea_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/user"):
        return httpx.Response(200, json={"login": "u"})
    if path.endswith("/user/repos"):
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "full_name": "acme/app",
                    "clone_url": "https://gitea.example/acme/app.git",
                    "default_branch": "main",
                    "private": False,
                }
            ],
        )
    if path.endswith("/branches"):
        return httpx.Response(
            200, json=[{"name": "main", "commit": {"id": SAMPLE_SHA}}]
        )
    if path.endswith("/tags"):
        return httpx.Response(200, json=[])
    if "/git/commits/" in path or "/branches/" in path:
        return httpx.Response(200, json={"sha": SAMPLE_SHA, "commit": {"id": SAMPLE_SHA}})
    if path.endswith("/pulls") and request.method == "POST":
        return httpx.Response(
            201,
            json={
                "id": 1,
                "number": 2,
                "html_url": "https://gitea.example/acme/app/pulls/2",
                "title": "docs",
                "state": "open",
                "head": {"sha": SAMPLE_SHA},
            },
        )
    if "/comments" in path:
        return httpx.Response(201, json={"id": 1})
    if "/statuses/" in path:
        return httpx.Response(201, json={"status": "success"})
    return httpx.Response(404, json={"message": path})


@pytest.mark.asyncio
async def test_gitea_conformance_mock() -> None:
    transport = httpx.MockTransport(_gitea_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GiteaProvider(token="t", api_base="https://gitea.example/api/v1", client=client)
        await provider.authenticate()
        repos = await provider.list_repos()
        assert repos[0].full_name == "acme/app"
        assert await provider.resolve_ref("acme/app", "main") == SAMPLE_SHA
        assert provider.supports_docs_as_code()


@pytest.mark.asyncio
async def test_upload_conformance(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "sample_repo"
    data = _zip_sample(fixture)
    provider = UploadProvider(archive_bytes=data, full_name="upload/sample")
    await provider.authenticate()
    repos = await provider.list_repos()
    assert repos[0].full_name == "upload/sample"
    sha = await provider.resolve_ref("upload/sample", "main")
    clone = await provider.shallow_clone("upload/sample", "main", tmp_path / "up")
    assert clone.commit_sha == sha
    assert (clone.path / "README.md").exists()


@pytest.mark.asyncio
async def test_generic_git_list_only() -> None:
    provider = GenericGitProvider(clone_url="https://example.com/acme/app.git")
    await provider.authenticate()
    repos = await provider.list_repos()
    assert repos[0].full_name == "acme/app"
    refs = await provider.list_refs("acme/app")
    assert refs[0].name == "main"


def test_factory_all_named() -> None:
    assert get_repo_provider("fixture").name == "fixture"
    with pytest.raises(ValueError):
        get_repo_provider("github", token="")
    with pytest.raises(ValueError):
        get_repo_provider("not-a-provider")
    p = get_repo_provider("upload", archive_bytes=_zip_sample(
        Path(__file__).parent / "fixtures" / "sample_repo"
    ))
    assert p.name == "upload"
    p2 = get_repo_provider(
        "generic_git", clone_url="https://example.com/o/r.git", token="x"
    )
    assert p2.name == "generic_git"
    # JSON round-trip sanity for mock payloads used in suite
    assert json.loads(json.dumps({"sha": SAMPLE_SHA}))["sha"] == SAMPLE_SHA

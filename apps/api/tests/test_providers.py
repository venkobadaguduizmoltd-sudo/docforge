"""RepoProvider fixture/GitHub/GitLab adapter tests."""

import pytest

from app.providers.factory import get_repo_provider
from app.providers.fixture import FixtureProvider


@pytest.mark.asyncio
async def test_fixture_provider_list_clone(tmp_path) -> None:
    provider = FixtureProvider()
    await provider.authenticate()
    repos = await provider.list_repos()
    assert repos and repos[0].full_name == "docforge/sample"
    refs = await provider.list_refs("docforge/sample")
    assert any(r.name == "main" for r in refs)
    sha = await provider.resolve_ref("docforge/sample", "main")
    assert len(sha) == 40
    clone = await provider.shallow_clone("docforge/sample", "main", tmp_path / "repo")
    assert clone.commit_sha == sha
    assert (clone.path / "README.md").exists()
    assert (clone.path / "src" / "app.py").exists()


def test_factory_unknown() -> None:
    with pytest.raises(ValueError):
        get_repo_provider("bitbucket")


def test_github_requires_token() -> None:
    with pytest.raises(ValueError):
        get_repo_provider("github", token="")

"""Gitea / Forgejo RepoProvider adapter (GitHub-compatible REST)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urlparse

import httpx

from app.providers.base import (
    CloneResult,
    CommitStatusInfo,
    PullRequestInfo,
    RemoteRepo,
    RepoProvider,
    RepoRef,
)
from app.providers.http_forge import git_shallow_clone


class GiteaProvider(RepoProvider):
    name = "gitea"

    def __init__(
        self,
        token: str,
        api_base: str = "https://gitea.com/api/v1",
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not token:
            raise ValueError("Gitea token is required")
        self.token = token
        self.api_base = api_base.rstrip("/")
        self._client = client
        self._owns_client = client is None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/json",
        }

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0, headers=self._headers())
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _host(self) -> str:
        parsed = urlparse(self.api_base)
        return parsed.hostname or "gitea.com"

    def supports_docs_as_code(self) -> bool:
        return True

    async def authenticate(self) -> None:
        client = await self._http()
        response = await client.get(f"{self.api_base}/user")
        response.raise_for_status()

    async def list_repos(self, query: str | None = None) -> list[RemoteRepo]:
        client = await self._http()
        if query:
            response = await client.get(
                f"{self.api_base}/repos/search",
                params={"q": query, "limit": 50},
            )
            response.raise_for_status()
            items = response.json().get("data", [])
        else:
            response = await client.get(
                f"{self.api_base}/user/repos",
                params={"limit": 50},
            )
            response.raise_for_status()
            items = response.json()
        return [
            RemoteRepo(
                id=str(item["id"]),
                full_name=item["full_name"],
                clone_url=item.get("clone_url") or "",
                default_branch=item.get("default_branch") or "main",
                private=bool(item.get("private")),
            )
            for item in items
        ]

    async def list_refs(self, full_name: str) -> list[RepoRef]:
        client = await self._http()
        refs: list[RepoRef] = []
        for kind, path in (("branch", "branches"), ("tag", "tags")):
            response = await client.get(
                f"{self.api_base}/repos/{full_name}/{path}",
                params={"limit": 50},
            )
            response.raise_for_status()
            for item in response.json():
                commit = item.get("commit") or {}
                sha = commit.get("id") or commit.get("sha") or item.get("id") or ""
                refs.append(RepoRef(name=item["name"], sha=sha, ref_type=kind))
        return refs

    async def resolve_ref(self, full_name: str, ref: str) -> str:
        client = await self._http()
        response = await client.get(
            f"{self.api_base}/repos/{full_name}/git/commits/{quote(ref, safe='')}"
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("sha") or data.get("id") or ""
        # branch endpoint
        response = await client.get(f"{self.api_base}/repos/{full_name}/branches/{quote(ref, safe='')}")
        response.raise_for_status()
        commit = response.json().get("commit") or {}
        return commit.get("id") or ""

    async def shallow_clone(
        self,
        full_name: str,
        ref: str,
        dest: Path,
        *,
        depth: int = 1,
    ) -> CloneResult:
        sha = await self.resolve_ref(full_name, ref)
        host = self._host()
        clone_url = f"https://oauth2:{self.token}@{host}/{full_name}.git"
        return await git_shallow_clone(
            clone_url=clone_url,
            ref=ref,
            sha=sha,
            dest=dest,
            depth=depth,
            provider=self.name,
            full_name=full_name,
        )

    async def create_docs_pull_request(
        self,
        full_name: str,
        *,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> PullRequestInfo:
        client = await self._http()
        response = await client.post(
            f"{self.api_base}/repos/{full_name}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch,
            },
        )
        response.raise_for_status()
        data = response.json()
        return PullRequestInfo(
            id=str(data["id"]),
            number=int(data["number"]),
            url=data.get("html_url") or data.get("url") or "",
            title=data.get("title") or title,
            state=data.get("state") or "open",
            head_sha=(data.get("head") or {}).get("sha") or "",
            base_ref=base_branch,
        )

    async def comment_on_pull_request(
        self,
        full_name: str,
        number: int,
        body: str,
    ) -> dict:
        client = await self._http()
        response = await client.post(
            f"{self.api_base}/repos/{full_name}/issues/{number}/comments",
            json={"body": body},
        )
        response.raise_for_status()
        return response.json()

    async def set_commit_status(
        self,
        full_name: str,
        sha: str,
        status: CommitStatusInfo,
    ) -> dict:
        client = await self._http()
        # Gitea uses pending/success/error/failure/warning
        response = await client.post(
            f"{self.api_base}/repos/{full_name}/statuses/{sha}",
            json={
                "context": status.context,
                "state": status.state,
                "description": status.description,
                "target_url": status.target_url,
            },
        )
        response.raise_for_status()
        return response.json()

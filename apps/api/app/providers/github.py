"""GitHub RepoProvider adapter (REST API + git shallow clone)."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import httpx

from app.providers.base import CloneResult, RemoteRepo, RepoProvider, RepoRef


class GitHubProvider(RepoProvider):
    name = "github"

    def __init__(
        self,
        token: str,
        api_base: str = "https://api.github.com",
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not token:
            raise ValueError("GitHub token is required")
        self.token = token
        self.api_base = api_base.rstrip("/")
        self._client = client
        self._owns_client = client is None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0, headers=self._headers())
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def authenticate(self) -> None:
        client = await self._http()
        response = await client.get(f"{self.api_base}/user")
        response.raise_for_status()

    async def list_repos(self, query: str | None = None) -> list[RemoteRepo]:
        client = await self._http()
        params: dict[str, str | int] = {"per_page": 100, "sort": "updated"}
        if query:
            # Search API for broader discovery; fall back to list if unused
            response = await client.get(
                f"{self.api_base}/search/repositories",
                params={"q": query, "per_page": 50},
            )
            response.raise_for_status()
            items = response.json().get("items", [])
        else:
            response = await client.get(f"{self.api_base}/user/repos", params=params)
            response.raise_for_status()
            items = response.json()
        return [
            RemoteRepo(
                id=str(item["id"]),
                full_name=item["full_name"],
                clone_url=item["clone_url"],
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
                params={"per_page": 100},
            )
            response.raise_for_status()
            for item in response.json():
                commit = item.get("commit") or {}
                sha = commit.get("sha") or item.get("sha") or ""
                refs.append(RepoRef(name=item["name"], sha=sha, ref_type=kind))
        return refs

    async def resolve_ref(self, full_name: str, ref: str) -> str:
        client = await self._http()
        response = await client.get(f"{self.api_base}/repos/{full_name}/commits/{ref}")
        response.raise_for_status()
        return response.json()["sha"]

    async def shallow_clone(
        self,
        full_name: str,
        ref: str,
        dest: Path,
        *,
        depth: int = 1,
    ) -> CloneResult:
        sha = await self.resolve_ref(full_name, ref)
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        clone_url = f"https://x-access-token:{self.token}@github.com/{full_name}.git"
        proc = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            "--depth",
            str(depth),
            "--branch",
            ref,
            clone_url,
            str(dest),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _out, err = await proc.communicate()
        if proc.returncode != 0:
            # Fall back: clone default then checkout SHA
            proc = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                "--depth",
                str(depth),
                clone_url,
                str(dest),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _out, err = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"git clone failed: {err.decode()}")
            checkout = await asyncio.create_subprocess_exec(
                "git",
                "-C",
                str(dest),
                "checkout",
                sha,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await checkout.communicate()
            if checkout.returncode != 0:
                raise RuntimeError(f"git checkout {sha} failed")
        return CloneResult(
            path=dest,
            commit_sha=sha,
            ref=ref,
            provider=self.name,
            full_name=full_name,
        )

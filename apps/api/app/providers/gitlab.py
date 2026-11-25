"""GitLab RepoProvider adapter (REST API + git shallow clone)."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from urllib.parse import quote

import httpx

from app.providers.base import CloneResult, RemoteRepo, RepoProvider, RepoRef


class GitLabProvider(RepoProvider):
    name = "gitlab"

    def __init__(
        self,
        token: str,
        api_base: str = "https://gitlab.com/api/v4",
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not token:
            raise ValueError("GitLab token is required")
        self.token = token
        self.api_base = api_base.rstrip("/")
        self._client = client
        self._owns_client = client is None

    def _headers(self) -> dict[str, str]:
        return {"PRIVATE-TOKEN": self.token}

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0, headers=self._headers())
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _project_path(self, full_name: str) -> str:
        return quote(full_name, safe="")

    async def authenticate(self) -> None:
        client = await self._http()
        response = await client.get(f"{self.api_base}/user")
        response.raise_for_status()

    async def list_repos(self, query: str | None = None) -> list[RemoteRepo]:
        client = await self._http()
        params: dict[str, str | int] = {"membership": "true", "per_page": 100}
        if query:
            params["search"] = query
        response = await client.get(f"{self.api_base}/projects", params=params)
        response.raise_for_status()
        return [
            RemoteRepo(
                id=str(item["id"]),
                full_name=item["path_with_namespace"],
                clone_url=item.get("http_url_to_repo") or item.get("ssh_url_to_repo", ""),
                default_branch=item.get("default_branch") or "main",
                private=item.get("visibility") != "public",
            )
            for item in response.json()
        ]

    async def list_refs(self, full_name: str) -> list[RepoRef]:
        client = await self._http()
        project = self._project_path(full_name)
        refs: list[RepoRef] = []
        for kind, path in (("branch", "repository/branches"), ("tag", "repository/tags")):
            response = await client.get(
                f"{self.api_base}/projects/{project}/{path}",
                params={"per_page": 100},
            )
            response.raise_for_status()
            for item in response.json():
                commit = item.get("commit") or {}
                refs.append(
                    RepoRef(
                        name=item["name"],
                        sha=commit.get("id") or item.get("target", ""),
                        ref_type=kind,
                    )
                )
        return refs

    async def resolve_ref(self, full_name: str, ref: str) -> str:
        client = await self._http()
        project = self._project_path(full_name)
        response = await client.get(
            f"{self.api_base}/projects/{project}/repository/commits/{quote(ref, safe='')}"
        )
        response.raise_for_status()
        return response.json()["id"]

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
        # Prefer HTTPS with oauth2 token
        host = "gitlab.com"
        if "gitlab" in self.api_base and "://" in self.api_base:
            # derive host from api_base when custom
            from urllib.parse import urlparse

            parsed = urlparse(self.api_base)
            if parsed.hostname:
                host = parsed.hostname
        clone_url = f"https://oauth2:{self.token}@{host}/{full_name}.git"
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

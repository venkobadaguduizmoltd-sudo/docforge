"""Bitbucket Cloud / Data Center RepoProvider adapter."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import httpx

from app.providers.base import CloneResult, RemoteRepo, RepoProvider, RepoRef
from app.providers.http_forge import git_shallow_clone


class BitbucketProvider(RepoProvider):
    """Supports Bitbucket Cloud (`api.bitbucket.org/2.0`) and DC (`/rest/api/1.0`)."""

    name = "bitbucket"

    def __init__(
        self,
        token: str,
        api_base: str = "https://api.bitbucket.org/2.0",
        *,
        username: str | None = None,
        workspace: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not token:
            raise ValueError("Bitbucket token is required")
        self.token = token
        self.username = username or ""
        self.workspace = workspace
        self.api_base = api_base.rstrip("/")
        self._is_dc = "/rest/api/" in self.api_base
        self._client = client
        self._owns_client = client is None

    def _headers(self) -> dict[str, str]:
        # Cloud: Bearer or Basic; DC: Bearer
        if self.username:
            import base64

            raw = f"{self.username}:{self.token}".encode()
            return {"Authorization": f"Basic {base64.b64encode(raw).decode()}"}
        return {"Authorization": f"Bearer {self.token}"}

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
        if self._is_dc:
            response = await client.get(f"{self.api_base}/users")
        else:
            response = await client.get(f"{self.api_base}/user")
        response.raise_for_status()

    async def list_repos(self, query: str | None = None) -> list[RemoteRepo]:
        client = await self._http()
        if self._is_dc:
            response = await client.get(f"{self.api_base}/repos", params={"limit": 100})
            response.raise_for_status()
            values = response.json().get("values", [])
            repos: list[RemoteRepo] = []
            for item in values:
                slug = item.get("slug") or item.get("name", "")
                project = (item.get("project") or {}).get("key", "")
                full_name = f"{project}/{slug}" if project else slug
                if query and query.lower() not in full_name.lower():
                    continue
                clone_links = item.get("links", {}).get("clone", [])
                http_url = next(
                    (c.get("href") for c in clone_links if c.get("name") == "http"),
                    "",
                )
                repos.append(
                    RemoteRepo(
                        id=str(item.get("id", full_name)),
                        full_name=full_name,
                        clone_url=http_url,
                        default_branch=(item.get("defaultBranch") or {}).get("displayId")
                        or "main",
                        private=not item.get("public", False),
                    )
                )
            return repos

        params: dict[str, str | int] = {"pagelen": 50}
        if self.workspace:
            url = f"{self.api_base}/repositories/{self.workspace}"
        else:
            url = f"{self.api_base}/repositories"
            params["role"] = "member"
        if query:
            params["q"] = f'name~"{query}"'
        response = await client.get(url, params=params)
        response.raise_for_status()
        values = response.json().get("values", [])
        out: list[RemoteRepo] = []
        for item in values:
            full_name = item.get("full_name") or ""
            clone_links = item.get("links", {}).get("clone", [])
            https = next(
                (c.get("href") for c in clone_links if c.get("name") == "https"),
                item.get("links", {}).get("html", {}).get("href", ""),
            )
            out.append(
                RemoteRepo(
                    id=item.get("uuid") or full_name,
                    full_name=full_name,
                    clone_url=https,
                    default_branch=item.get("mainbranch", {}).get("name") or "main",
                    private=item.get("is_private", True),
                )
            )
        return out

    async def list_refs(self, full_name: str) -> list[RepoRef]:
        client = await self._http()
        refs: list[RepoRef] = []
        if self._is_dc:
            project, slug = full_name.split("/", 1)
            for kind, path in (("branch", "branches"), ("tag", "tags")):
                response = await client.get(
                    f"{self.api_base}/projects/{project}/repos/{slug}/{path}",
                    params={"limit": 100},
                )
                response.raise_for_status()
                for item in response.json().get("values", []):
                    refs.append(
                        RepoRef(
                            name=item.get("displayId") or item.get("id", ""),
                            sha=(item.get("latestCommit") or ""),
                            ref_type=kind,
                        )
                    )
            return refs

        workspace, repo_slug = full_name.split("/", 1)
        for kind, path in (("branch", "refs/branches"), ("tag", "refs/tags")):
            response = await client.get(
                f"{self.api_base}/repositories/{workspace}/{repo_slug}/{path}",
                params={"pagelen": 100},
            )
            response.raise_for_status()
            for item in response.json().get("values", []):
                target = item.get("target") or {}
                refs.append(
                    RepoRef(
                        name=item.get("name", ""),
                        sha=target.get("hash") or "",
                        ref_type=kind,
                    )
                )
        return refs

    async def resolve_ref(self, full_name: str, ref: str) -> str:
        refs = await self.list_refs(full_name)
        for item in refs:
            if item.name == ref:
                return item.sha
        if len(ref) >= 40:
            return ref[:40].lower()
        # Cloud commit lookup
        if not self._is_dc:
            client = await self._http()
            workspace, repo_slug = full_name.split("/", 1)
            response = await client.get(
                f"{self.api_base}/repositories/{workspace}/{repo_slug}/commit/{quote(ref, safe='')}"
            )
            response.raise_for_status()
            return response.json()["hash"]
        raise ValueError(f"Unknown ref: {ref}")

    def _auth_clone_url(self, clone_url: str) -> str:
        if not clone_url.startswith("http"):
            return clone_url
        if self.username:
            return clone_url.replace(
                "https://", f"https://{self.username}:{self.token}@", 1
            )
        return clone_url.replace("https://", f"https://x-token-auth:{self.token}@", 1)

    async def shallow_clone(
        self,
        full_name: str,
        ref: str,
        dest: Path,
        *,
        depth: int = 1,
    ) -> CloneResult:
        sha = await self.resolve_ref(full_name, ref)
        repos = await self.list_repos()
        match = next((r for r in repos if r.full_name == full_name), None)
        if match and match.clone_url:
            clone_url = self._auth_clone_url(match.clone_url)
        elif self._is_dc:
            clone_url = full_name  # caller should pass clone_url via list
            raise RuntimeError("Bitbucket DC clone requires clone_url from list_repos")
        else:
            workspace, repo_slug = full_name.split("/", 1)
            clone_url = self._auth_clone_url(
                f"https://bitbucket.org/{workspace}/{repo_slug}.git"
            )
        return await git_shallow_clone(
            clone_url=clone_url,
            ref=ref,
            sha=sha,
            dest=dest,
            depth=depth,
            provider=self.name,
            full_name=full_name,
        )

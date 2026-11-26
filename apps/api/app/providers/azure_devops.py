"""Azure DevOps Git RepoProvider adapter."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import httpx

from app.providers.base import CloneResult, RemoteRepo, RepoProvider, RepoRef
from app.providers.http_forge import git_shallow_clone


class AzureDevOpsProvider(RepoProvider):
    name = "azure_devops"

    def __init__(
        self,
        token: str,
        *,
        organization: str,
        project: str | None = None,
        api_base: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not token:
            raise ValueError("Azure DevOps token is required")
        if not organization:
            raise ValueError("Azure DevOps organization is required")
        self.token = token
        self.organization = organization
        self.project = project
        self.api_base = (api_base or f"https://dev.azure.com/{organization}").rstrip("/")
        self._client = client
        self._owns_client = client is None

    def _headers(self) -> dict[str, str]:
        import base64

        raw = f":{self.token}".encode()
        return {
            "Authorization": f"Basic {base64.b64encode(raw).decode()}",
            "Content-Type": "application/json",
        }

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0, headers=self._headers())
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _project_segment(self) -> str:
        if not self.project:
            raise ValueError("Azure DevOps project is required for this operation")
        return quote(self.project, safe="")

    async def authenticate(self) -> None:
        client = await self._http()
        response = await client.get(
            f"{self.api_base}/_apis/projects",
            params={"api-version": "7.1"},
        )
        response.raise_for_status()

    async def list_repos(self, query: str | None = None) -> list[RemoteRepo]:
        client = await self._http()
        if self.project:
            url = f"{self.api_base}/{self._project_segment()}/_apis/git/repositories"
        else:
            url = f"{self.api_base}/_apis/git/repositories"
        response = await client.get(url, params={"api-version": "7.1"})
        response.raise_for_status()
        values = response.json().get("value", [])
        out: list[RemoteRepo] = []
        for item in values:
            name = item.get("name") or ""
            project_name = (item.get("project") or {}).get("name") or self.project or ""
            full_name = f"{project_name}/{name}" if project_name else name
            if query and query.lower() not in full_name.lower():
                continue
            out.append(
                RemoteRepo(
                    id=item.get("id") or full_name,
                    full_name=full_name,
                    clone_url=item.get("remoteUrl") or item.get("webUrl") or "",
                    default_branch=(item.get("defaultBranch") or "refs/heads/main").replace(
                        "refs/heads/", ""
                    ),
                    private=True,
                    extra={"project": project_name},
                )
            )
        return out

    def _split_full_name(self, full_name: str) -> tuple[str, str]:
        if "/" in full_name:
            project, repo = full_name.split("/", 1)
            return project, repo
        if self.project:
            return self.project, full_name
        raise ValueError("full_name must be project/repo")

    async def list_refs(self, full_name: str) -> list[RepoRef]:
        client = await self._http()
        project, repo = self._split_full_name(full_name)
        response = await client.get(
            f"{self.api_base}/{quote(project, safe='')}/_apis/git/repositories/"
            f"{quote(repo, safe='')}/refs",
            params={"api-version": "7.1"},
        )
        response.raise_for_status()
        refs: list[RepoRef] = []
        for item in response.json().get("value", []):
            name = item.get("name") or ""
            if name.startswith("refs/heads/"):
                refs.append(
                    RepoRef(
                        name=name.removeprefix("refs/heads/"),
                        sha=item.get("objectId") or "",
                        ref_type="branch",
                    )
                )
            elif name.startswith("refs/tags/"):
                refs.append(
                    RepoRef(
                        name=name.removeprefix("refs/tags/"),
                        sha=item.get("objectId") or "",
                        ref_type="tag",
                    )
                )
        return refs

    async def resolve_ref(self, full_name: str, ref: str) -> str:
        refs = await self.list_refs(full_name)
        for item in refs:
            if item.name == ref:
                return item.sha
        if len(ref) == 40 and all(c in "0123456789abcdef" for c in ref.lower()):
            return ref.lower()
        client = await self._http()
        project, repo = self._split_full_name(full_name)
        response = await client.get(
            f"{self.api_base}/{quote(project, safe='')}/_apis/git/repositories/"
            f"{quote(repo, safe='')}/commits",
            params={"searchCriteria.itemVersion.version": ref, "api-version": "7.1", "$top": 1},
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        if not values:
            raise ValueError(f"Unknown ref: {ref}")
        return values[0]["commitId"]

    async def shallow_clone(
        self,
        full_name: str,
        ref: str,
        dest: Path,
        *,
        depth: int = 1,
    ) -> CloneResult:
        sha = await self.resolve_ref(full_name, ref)
        project, repo = self._split_full_name(full_name)
        clone_url = (
            f"https://{self.organization}:{self.token}@dev.azure.com/"
            f"{self.organization}/{quote(project, safe='')}/_git/{quote(repo, safe='')}"
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

"""Fixture RepoProvider for CI — copies a local sample repo, no network."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from app.providers.base import (
    CloneResult,
    CommitStatusInfo,
    PullRequestInfo,
    RemoteRepo,
    RepoProvider,
    RepoRef,
)

DEFAULT_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "sample_repo"


class FixtureProvider(RepoProvider):
    name = "fixture"

    def supports_docs_as_code(self) -> bool:
        return True

    def __init__(self, fixture_root: Path | None = None) -> None:
        self.fixture_root = fixture_root or DEFAULT_FIXTURE
        if not self.fixture_root.exists():
            raise FileNotFoundError(f"Fixture repo missing: {self.fixture_root}")

    def _sha_for(self, ref: str) -> str:
        payload = f"fixture:{self.fixture_root}:{ref}".encode()
        return hashlib.sha1(payload).hexdigest()  # noqa: S324 — pin id only, not crypto

    async def authenticate(self) -> None:
        return None

    async def list_repos(self, query: str | None = None) -> list[RemoteRepo]:
        name = "docforge/sample"
        if query and query.lower() not in name:
            return []
        return [
            RemoteRepo(
                id="fixture-1",
                full_name=name,
                clone_url=str(self.fixture_root),
                default_branch="main",
                private=False,
            )
        ]

    async def list_refs(self, full_name: str) -> list[RepoRef]:
        return [
            RepoRef(name="main", sha=self._sha_for("main"), ref_type="branch"),
            RepoRef(name="v1.0.0", sha=self._sha_for("v1.0.0"), ref_type="tag"),
        ]

    async def resolve_ref(self, full_name: str, ref: str) -> str:
        known = {r.name: r.sha for r in await self.list_refs(full_name)}
        if ref in known:
            return known[ref]
        if len(ref) == 40 and all(c in "0123456789abcdef" for c in ref.lower()):
            return ref.lower()
        return self._sha_for(ref)

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
        shutil.copytree(self.fixture_root, dest)
        return CloneResult(
            path=dest,
            commit_sha=sha,
            ref=ref,
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
        return PullRequestInfo(
            id="fixture-pr-1",
            number=1,
            url=f"https://fixture.local/{full_name}/pull/1",
            title=title,
            state="open",
            head_sha=self._sha_for(head_branch),
            base_ref=base_branch,
        )

    async def comment_on_pull_request(
        self,
        full_name: str,
        number: int,
        body: str,
    ) -> dict[str, Any]:
        return {"id": 1, "body": body, "full_name": full_name, "number": number}

    async def set_commit_status(
        self,
        full_name: str,
        sha: str,
        status: CommitStatusInfo,
    ) -> dict[str, Any]:
        return {
            "full_name": full_name,
            "sha": sha,
            "context": status.context,
            "state": status.state,
            "description": status.description,
        }

"""RepoProvider abstraction — authenticate, list, resolve, shallow clone, docs-as-code."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RepoRef:
    name: str
    sha: str
    ref_type: str = "branch"  # branch | tag | commit


@dataclass(frozen=True)
class RemoteRepo:
    id: str
    full_name: str
    clone_url: str
    default_branch: str
    private: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CloneResult:
    path: Path
    commit_sha: str
    ref: str
    provider: str
    full_name: str


@dataclass(frozen=True)
class PullRequestInfo:
    id: str
    number: int
    url: str
    title: str
    state: str
    head_sha: str
    base_ref: str


@dataclass(frozen=True)
class CommitStatusInfo:
    context: str
    state: str  # pending | success | failure | error
    description: str
    target_url: str | None = None


class RepoProvider(ABC):
    """Git hosting adapter interface."""

    name: str

    @abstractmethod
    async def authenticate(self) -> None:
        """Validate credentials; raise on failure."""

    @abstractmethod
    async def list_repos(self, query: str | None = None) -> list[RemoteRepo]:
        """List accessible repositories."""

    @abstractmethod
    async def list_refs(self, full_name: str) -> list[RepoRef]:
        """List branches/tags (and optionally known commits)."""

    @abstractmethod
    async def resolve_ref(self, full_name: str, ref: str) -> str:
        """Resolve branch/tag/ref to a commit SHA."""

    @abstractmethod
    async def shallow_clone(
        self,
        full_name: str,
        ref: str,
        dest: Path,
        *,
        depth: int = 1,
    ) -> CloneResult:
        """Shallow clone pinned to the resolved commit SHA."""

    # --- Docs-as-code (optional; raise NotImplementedError if unsupported) ---

    async def create_docs_pull_request(
        self,
        full_name: str,
        *,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> PullRequestInfo:
        raise NotImplementedError(f"{self.name} does not support docs-as-code PRs")

    async def comment_on_pull_request(
        self,
        full_name: str,
        number: int,
        body: str,
    ) -> dict[str, Any]:
        raise NotImplementedError(f"{self.name} does not support PR comments")

    async def set_commit_status(
        self,
        full_name: str,
        sha: str,
        status: CommitStatusInfo,
    ) -> dict[str, Any]:
        raise NotImplementedError(f"{self.name} does not support commit statuses")

    def supports_docs_as_code(self) -> bool:
        return False

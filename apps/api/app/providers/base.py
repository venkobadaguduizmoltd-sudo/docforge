"""RepoProvider abstraction — authenticate, list, resolve, shallow clone."""

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

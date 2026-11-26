"""Git hosting providers."""

from app.providers.base import (
    CloneResult,
    CommitStatusInfo,
    PullRequestInfo,
    RemoteRepo,
    RepoProvider,
    RepoRef,
)
from app.providers.factory import KNOWN_PROVIDERS, get_repo_provider

__all__ = [
    "KNOWN_PROVIDERS",
    "CloneResult",
    "CommitStatusInfo",
    "PullRequestInfo",
    "RemoteRepo",
    "RepoProvider",
    "RepoRef",
    "get_repo_provider",
]

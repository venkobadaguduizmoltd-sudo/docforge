"""Git hosting providers."""

from app.providers.base import CloneResult, RemoteRepo, RepoProvider, RepoRef
from app.providers.factory import get_repo_provider

__all__ = [
    "CloneResult",
    "RemoteRepo",
    "RepoProvider",
    "RepoRef",
    "get_repo_provider",
]

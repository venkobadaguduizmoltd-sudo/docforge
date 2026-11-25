"""Build a RepoProvider from settings / request parameters."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.providers.base import RepoProvider
from app.providers.fixture import FixtureProvider
from app.providers.github import GitHubProvider
from app.providers.gitlab import GitLabProvider


def get_repo_provider(
    provider: str,
    *,
    token: str | None = None,
    api_base: str | None = None,
    settings: Settings | None = None,
) -> RepoProvider:
    settings = settings or get_settings()
    name = provider.lower().strip()
    if name == "fixture":
        return FixtureProvider()
    if name == "github":
        return GitHubProvider(
            token=token or settings.github_token,
            api_base=api_base or settings.github_api_base,
        )
    if name == "gitlab":
        return GitLabProvider(
            token=token or settings.gitlab_token,
            api_base=api_base or settings.gitlab_api_base,
        )
    raise ValueError(f"Unknown repo provider: {provider}")

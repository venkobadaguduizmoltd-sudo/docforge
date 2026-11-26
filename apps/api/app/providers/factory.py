"""Build a RepoProvider from settings / request parameters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.providers.azure_devops import AzureDevOpsProvider
from app.providers.base import RepoProvider
from app.providers.bitbucket import BitbucketProvider
from app.providers.fixture import FixtureProvider
from app.providers.generic_git import GenericGitProvider
from app.providers.gitea import GiteaProvider
from app.providers.github import GitHubProvider
from app.providers.gitlab import GitLabProvider
from app.providers.upload import UploadProvider

KNOWN_PROVIDERS = (
    "fixture",
    "github",
    "gitlab",
    "bitbucket",
    "azure_devops",
    "gitea",
    "generic_git",
    "upload",
)


def get_repo_provider(
    provider: str,
    *,
    token: str | None = None,
    api_base: str | None = None,
    settings: Settings | None = None,
    **kwargs: Any,
) -> RepoProvider:
    settings = settings or get_settings()
    name = provider.lower().strip()
    if name == "fixture":
        return FixtureProvider()
    if name == "github":
        return GitHubProvider(
            token=token or settings.github_token,
            api_base=api_base or settings.github_api_base,
            client=kwargs.get("client"),
        )
    if name == "gitlab":
        return GitLabProvider(
            token=token or settings.gitlab_token,
            api_base=api_base or settings.gitlab_api_base,
            client=kwargs.get("client"),
        )
    if name == "bitbucket":
        return BitbucketProvider(
            token=token or settings.bitbucket_token,
            api_base=api_base or settings.bitbucket_api_base,
            username=kwargs.get("username") or settings.bitbucket_username or None,
            workspace=kwargs.get("workspace") or settings.bitbucket_workspace or None,
            client=kwargs.get("client"),
        )
    if name in ("azure_devops", "azure", "ado"):
        org = kwargs.get("organization") or settings.azure_devops_org
        project = kwargs.get("project") or settings.azure_devops_project or None
        return AzureDevOpsProvider(
            token=token or settings.azure_devops_token,
            organization=org,
            project=project,
            api_base=api_base,
            client=kwargs.get("client"),
        )
    if name in ("gitea", "forgejo"):
        return GiteaProvider(
            token=token or settings.gitea_token,
            api_base=api_base or settings.gitea_api_base,
            client=kwargs.get("client"),
        )
    if name == "generic_git":
        clone_url = kwargs.get("clone_url") or ""
        if not clone_url:
            raise ValueError("generic_git requires clone_url")
        return GenericGitProvider(
            clone_url=clone_url,
            token=token,
            ssh_key_path=kwargs.get("ssh_key_path"),
            default_branch=kwargs.get("default_branch") or "main",
            full_name=kwargs.get("full_name"),
        )
    if name == "upload":
        archive_bytes = kwargs.get("archive_bytes")
        archive_path = kwargs.get("archive_path")
        if archive_path is not None and not isinstance(archive_path, Path):
            archive_path = Path(archive_path)
        return UploadProvider(
            archive_bytes=archive_bytes,
            archive_path=archive_path,
            full_name=kwargs.get("full_name") or "upload/local",
            default_branch=kwargs.get("default_branch") or "main",
        )
    raise ValueError(f"Unknown repo provider: {provider}")

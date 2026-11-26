"""Open docs PR/MR with generated content, comments, and commit status checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.providers.base import CommitStatusInfo, PullRequestInfo, RepoProvider


@dataclass
class DocsAsCodeResult:
    pull_request: PullRequestInfo
    comment: dict[str, Any] | None
    status: dict[str, Any] | None


async def open_docs_pull_request(
    provider: RepoProvider,
    *,
    full_name: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
    head_sha: str | None = None,
    comment_body: str | None = None,
    status_context: str = "docforge/docs",
    status_description: str = "Documentation generated",
    target_url: str | None = None,
) -> DocsAsCodeResult:
    if not provider.supports_docs_as_code():
        raise NotImplementedError(f"{provider.name} does not support docs-as-code")

    pr = await provider.create_docs_pull_request(
        full_name,
        head_branch=head_branch,
        base_branch=base_branch,
        title=title,
        body=body,
    )
    comment: dict[str, Any] | None = None
    if comment_body:
        comment = await provider.comment_on_pull_request(full_name, pr.number, comment_body)

    status: dict[str, Any] | None = None
    sha = head_sha or pr.head_sha
    if sha:
        status = await provider.set_commit_status(
            full_name,
            sha,
            CommitStatusInfo(
                context=status_context,
                state="success",
                description=status_description,
                target_url=target_url or pr.url,
            ),
        )
    return DocsAsCodeResult(pull_request=pr, comment=comment, status=status)


def build_docs_pr_body(
    *,
    template_slug: str,
    commit_sha: str,
    sections: list[str] | None = None,
    drift_summary: str | None = None,
) -> str:
    lines = [
        "## DocForge generated documentation",
        "",
        f"- Template: `{template_slug}`",
        f"- Pinned commit: `{commit_sha}`",
    ]
    if sections:
        lines.append(f"- Sections: {', '.join(f'`{s}`' for s in sections)}")
    if drift_summary:
        lines.extend(["", "### Drift", drift_summary])
    lines.extend(["", "---", "_Opened automatically by DocForge docs-as-code._"])
    return "\n".join(lines)

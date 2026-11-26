"""Normalize forge webhook payloads into a common event shape."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NormalizedWebhookEvent:
    provider: str
    event_type: str  # push | pull_request | ping | unknown
    delivery_id: str
    full_name: str
    ref: str | None = None
    before_sha: str | None = None
    after_sha: str | None = None
    action: str | None = None
    pr_number: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def normalize_webhook_event(
    provider: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> NormalizedWebhookEvent:
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    name = provider.lower().strip()

    if name == "github":
        event = headers.get("x-github-event", "unknown")
        delivery = headers.get("x-github-delivery", "")
        repo = payload.get("repository") or {}
        full_name = repo.get("full_name") or ""
        if event == "push":
            return NormalizedWebhookEvent(
                provider=name,
                event_type="push",
                delivery_id=delivery,
                full_name=full_name,
                ref=payload.get("ref"),
                before_sha=payload.get("before"),
                after_sha=payload.get("after"),
                raw=payload,
            )
        if event in ("pull_request", "pull_request_review"):
            pr = payload.get("pull_request") or {}
            return NormalizedWebhookEvent(
                provider=name,
                event_type="pull_request",
                delivery_id=delivery,
                full_name=full_name,
                ref=(pr.get("head") or {}).get("ref"),
                after_sha=(pr.get("head") or {}).get("sha"),
                action=payload.get("action"),
                pr_number=pr.get("number"),
                raw=payload,
            )
        if event == "ping":
            return NormalizedWebhookEvent(
                provider=name,
                event_type="ping",
                delivery_id=delivery,
                full_name=full_name,
                raw=payload,
            )

    if name == "gitlab":
        event = headers.get("x-gitlab-event", payload.get("object_kind", "unknown"))
        delivery = headers.get("x-gitlab-event-uuid") or str(payload.get("checkout_sha") or "")
        project = payload.get("project") or {}
        full_name = project.get("path_with_namespace") or ""
        kind = str(event).lower()
        if "push" in kind or payload.get("object_kind") == "push":
            return NormalizedWebhookEvent(
                provider=name,
                event_type="push",
                delivery_id=delivery or f"gl-push-{payload.get('checkout_sha')}",
                full_name=full_name,
                ref=payload.get("ref"),
                before_sha=payload.get("before"),
                after_sha=payload.get("after") or payload.get("checkout_sha"),
                raw=payload,
            )
        if "merge request" in kind or payload.get("object_kind") == "merge_request":
            attrs = payload.get("object_attributes") or {}
            return NormalizedWebhookEvent(
                provider=name,
                event_type="pull_request",
                delivery_id=delivery or f"gl-mr-{attrs.get('iid')}",
                full_name=full_name,
                ref=attrs.get("source_branch"),
                after_sha=attrs.get("last_commit", {}).get("id")
                if isinstance(attrs.get("last_commit"), dict)
                else None,
                action=attrs.get("action"),
                pr_number=attrs.get("iid"),
                raw=payload,
            )

    if name == "bitbucket":
        delivery = headers.get("x-request-uuid") or headers.get("x-hook-uuid") or ""
        event = headers.get("x-event-key", "unknown")
        repo = payload.get("repository") or {}
        full_name = repo.get("full_name") or ""
        if "push" in event:
            changes = (payload.get("push") or {}).get("changes") or []
            change = changes[0] if changes else {}
            new = change.get("new") or {}
            old = change.get("old") or {}
            return NormalizedWebhookEvent(
                provider=name,
                event_type="push",
                delivery_id=delivery,
                full_name=full_name,
                ref=new.get("name"),
                before_sha=(old.get("target") or {}).get("hash"),
                after_sha=(new.get("target") or {}).get("hash"),
                raw=payload,
            )
        if "pullrequest" in event:
            pr = payload.get("pullrequest") or {}
            return NormalizedWebhookEvent(
                provider=name,
                event_type="pull_request",
                delivery_id=delivery,
                full_name=full_name,
                ref=(pr.get("source") or {}).get("branch", {}).get("name"),
                after_sha=(pr.get("source") or {}).get("commit", {}).get("hash"),
                action=event.split(":")[-1] if ":" in event else event,
                pr_number=pr.get("id"),
                raw=payload,
            )

    if name in ("gitea", "forgejo"):
        event = headers.get("x-gitea-event") or headers.get("x-github-event") or "unknown"
        delivery = headers.get("x-gitea-delivery") or headers.get("x-github-delivery") or ""
        repo = payload.get("repository") or {}
        full_name = repo.get("full_name") or ""
        if event == "push":
            return NormalizedWebhookEvent(
                provider="gitea",
                event_type="push",
                delivery_id=delivery,
                full_name=full_name,
                ref=payload.get("ref"),
                before_sha=payload.get("before"),
                after_sha=payload.get("after"),
                raw=payload,
            )
        if event == "pull_request":
            pr = payload.get("pull_request") or {}
            return NormalizedWebhookEvent(
                provider="gitea",
                event_type="pull_request",
                delivery_id=delivery,
                full_name=full_name,
                ref=(pr.get("head") or {}).get("ref"),
                after_sha=(pr.get("head") or {}).get("sha"),
                action=payload.get("action"),
                pr_number=pr.get("number"),
                raw=payload,
            )

    if name in ("azure_devops", "azure", "ado"):
        event_type = payload.get("eventType") or "unknown"
        delivery = str(payload.get("id") or "")
        resource = payload.get("resource") or {}
        repo = resource.get("repository") or {}
        full_name = repo.get("name") or ""
        if "git.push" in event_type:
            ref_updates = resource.get("refUpdates") or []
            update = ref_updates[0] if ref_updates else {}
            return NormalizedWebhookEvent(
                provider="azure_devops",
                event_type="push",
                delivery_id=delivery,
                full_name=full_name,
                ref=update.get("name"),
                before_sha=update.get("oldObjectId"),
                after_sha=update.get("newObjectId"),
                raw=payload,
            )
        if "pullrequest" in event_type.lower():
            return NormalizedWebhookEvent(
                provider="azure_devops",
                event_type="pull_request",
                delivery_id=delivery,
                full_name=full_name,
                ref=(resource.get("sourceRefName") or "").removeprefix("refs/heads/"),
                after_sha=(resource.get("lastMergeSourceCommit") or {}).get("commitId"),
                action=event_type.split(".")[-1],
                pr_number=resource.get("pullRequestId"),
                raw=payload,
            )

    return NormalizedWebhookEvent(
        provider=name,
        event_type="unknown",
        delivery_id=headers.get("x-delivery-id", ""),
        full_name="",
        raw=payload,
    )

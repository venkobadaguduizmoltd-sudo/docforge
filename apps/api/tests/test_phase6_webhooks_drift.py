"""Phase 6 — webhooks, docs-as-code, and drift tests."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.integrations.docs_as_code import build_docs_pr_body, open_docs_pull_request
from app.integrations.drift import (
    compute_changed_files,
    detect_drift,
    incremental_regen_plan,
    map_changed_files_to_sections,
)
from app.main import create_app
from app.providers.fixture import FixtureProvider
from app.webhooks.normalize import normalize_webhook_event
from app.webhooks.replay import reset_replay_guard
from app.webhooks.store import webhook_store
from app.webhooks.verify import verify_webhook_signature


def test_verify_github_signature() -> None:
    secret = "s3cret"
    body = b'{"ok":true}'
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(
        provider="github",
        body=body,
        secret=secret,
        signature_header=f"sha256={digest}",
    )
    assert not verify_webhook_signature(
        provider="github",
        body=body,
        secret=secret,
        signature_header="sha256=deadbeef",
    )


def test_verify_gitlab_token() -> None:
    assert verify_webhook_signature(
        provider="gitlab",
        body=b"{}",
        secret="tok",
        signature_header="tok",
    )


def test_normalize_github_push() -> None:
    event = normalize_webhook_event(
        "github",
        {
            "ref": "refs/heads/main",
            "before": "a" * 40,
            "after": "b" * 40,
            "repository": {"full_name": "acme/app"},
        },
        headers={"X-GitHub-Event": "push", "X-GitHub-Delivery": "d1"},
    )
    assert event.event_type == "push"
    assert event.full_name == "acme/app"
    assert event.after_sha == "b" * 40


def test_normalize_gitlab_mr() -> None:
    event = normalize_webhook_event(
        "gitlab",
        {
            "object_kind": "merge_request",
            "project": {"path_with_namespace": "acme/app"},
            "object_attributes": {
                "iid": 5,
                "source_branch": "feat",
                "action": "open",
                "last_commit": {"id": "c" * 40},
            },
        },
        headers={"X-Gitlab-Event": "Merge Request Hook", "X-Gitlab-Event-UUID": "u1"},
    )
    assert event.event_type == "pull_request"
    assert event.pr_number == 5


def test_replay_guard() -> None:
    guard = reset_replay_guard(ttl_seconds=60)
    assert guard.check_and_remember("del-1", now=1000.0)
    assert not guard.check_and_remember("del-1", now=1001.0)
    assert not guard.check_and_remember("del-2", timestamp=100.0, now=1000.0)


def test_map_sections() -> None:
    sections = map_changed_files_to_sections(
        ["src/app.py", "openapi.yaml", "requirements.txt"]
    )
    assert "architecture" in sections
    assert "api" in sections
    assert "dependencies" in sections


def test_compute_changed_files(tmp_path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "README.md").write_text("one")
    (b / "README.md").write_text("two")
    (b / "new.py").write_text("x")
    changed = compute_changed_files(a, b)
    assert "README.md" in changed
    assert "new.py" in changed


@pytest.mark.asyncio
async def test_detect_drift_and_plan() -> None:
    provider = FixtureProvider()
    pinned = await provider.resolve_ref("docforge/sample", "main")
    report = await detect_drift(
        provider=provider,
        full_name="docforge/sample",
        base_ref="main",
        pinned_sha=pinned,
    )
    assert report.is_drifted is False
    plan = incremental_regen_plan(report)
    assert plan["mode"] == "noop"

    report2 = await detect_drift(
        provider=provider,
        full_name="docforge/sample",
        base_ref="main",
        pinned_sha="0" * 40,
        changed_files=["src/app.py"],
    )
    assert report2.is_drifted is True
    plan2 = incremental_regen_plan(report2)
    assert plan2["mode"] == "incremental"
    assert "architecture" in plan2["sections"]


@pytest.mark.asyncio
async def test_docs_as_code_fixture() -> None:
    provider = FixtureProvider()
    body = build_docs_pr_body(template_slug="tech-overview", commit_sha="abc", sections=["overview"])
    assert "tech-overview" in body
    result = await open_docs_pull_request(
        provider,
        full_name="docforge/sample",
        head_branch="docs/docforge",
        base_branch="main",
        title="docs: update",
        body=body,
        head_sha="a" * 40,
        comment_body="generated",
    )
    assert result.pull_request.number == 1
    assert result.comment is not None
    assert result.status is not None


class _FakeUser:
    id = "test-user"
    email = "admin@localhost"
    role = "admin"
    is_active = True


@pytest.mark.asyncio
async def test_webhook_api_flow() -> None:
    reset_replay_guard()
    webhook_store._items.clear()
    app = create_app()

    from app.rbac.deps import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _FakeUser()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer test"}
            reg = await client.post(
                "/webhooks/register",
                headers=headers,
                json={"provider": "github", "full_name": "acme/app", "secret": "whsec"},
            )
            assert reg.status_code == 200, reg.text
            secret = reg.json()["secret"]
            body = {
                "ref": "refs/heads/main",
                "before": "a" * 40,
                "after": "b" * 40,
                "repository": {"full_name": "acme/app"},
            }
            raw = json.dumps(body).encode()
            sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
            resp = await client.post(
                "/webhooks/github/deliver",
                content=raw,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": f"sha256={sig}",
                    "X-GitHub-Event": "push",
                    "X-GitHub-Delivery": "delivery-unique-1",
                },
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["event"]["event_type"] == "push"

            resp2 = await client.post(
                "/webhooks/github/deliver",
                content=raw,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": f"sha256={sig}",
                    "X-GitHub-Event": "push",
                    "X-GitHub-Delivery": "delivery-unique-1",
                },
            )
            assert resp2.status_code == 409

            drift = await client.post(
                "/integrations/drift",
                headers=headers,
                json={
                    "provider": "fixture",
                    "full_name": "docforge/sample",
                    "base_ref": "main",
                    "pinned_sha": "0" * 40,
                    "changed_files": ["README.md"],
                },
            )
            assert drift.status_code == 200
            assert drift.json()["drift"]["is_drifted"] is True

            docs = await client.post(
                "/integrations/docs-as-code",
                headers=headers,
                json={
                    "provider": "fixture",
                    "full_name": "docforge/sample",
                    "head_branch": "docs/x",
                    "base_branch": "main",
                    "commit_sha": "a" * 40,
                },
            )
            assert docs.status_code == 200
            assert docs.json()["pull_request"]["number"] == 1
    finally:
        app.dependency_overrides.clear()

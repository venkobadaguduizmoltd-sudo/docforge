"""Webhook registration and inbound delivery endpoints."""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.rbac.deps import get_current_user
from app.webhooks.normalize import normalize_webhook_event
from app.webhooks.replay import get_replay_guard
from app.webhooks.store import webhook_store
from app.webhooks.verify import verify_webhook_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class RegisterWebhookRequest(BaseModel):
    provider: str
    full_name: str
    secret: str | None = None
    events: list[str] = Field(default_factory=lambda: ["push", "pull_request"])
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/register")
async def register_webhook(body: RegisterWebhookRequest, _user=Depends(get_current_user)) -> dict:
    item = webhook_store.register(
        provider=body.provider,
        full_name=body.full_name,
        secret=body.secret,
        events=body.events,
        metadata=body.metadata,
    )
    public = item.to_public()
    # Return secret once at registration time
    public["secret"] = item.secret
    return public


@router.get("")
async def list_webhooks(provider: str | None = None, _user=Depends(get_current_user)) -> dict:
    items = webhook_store.list_for(provider)
    return {"webhooks": [i.to_public() for i in items]}


@router.post("/{provider}/deliver")
async def receive_webhook(
    provider: str,
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_hub_signature: str | None = Header(default=None),
    x_gitlab_token: str | None = Header(default=None),
    x_gitea_signature: str | None = Header(default=None),
    webhook_id: str | None = None,
) -> dict:
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()}

    # Resolve registration secret
    registration = None
    if webhook_id:
        registration = webhook_store.get(webhook_id)
    try:
        payload = json.loads(body.decode() or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    if registration is None:
        # Best-effort match after normalize for full_name
        event_preview = normalize_webhook_event(provider, payload, headers=headers)
        registration = webhook_store.find_by_repo(provider, event_preview.full_name)

    if registration is None:
        raise HTTPException(status_code=404, detail="No webhook registration found")

    signature = (
        x_hub_signature_256
        or x_gitea_signature
        or x_hub_signature
        or x_gitlab_token
        or headers.get("x-ado-signature")
    )
    if not verify_webhook_signature(
        provider=provider,
        body=body,
        secret=registration.secret,
        signature_header=signature,
        alt_header=x_gitlab_token,
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event = normalize_webhook_event(provider, payload, headers=headers)
    ts_header = headers.get("x-hub-timestamp") or headers.get("x-request-timestamp")
    timestamp = float(ts_header) if ts_header else None
    if not get_replay_guard().check_and_remember(
        event.delivery_id or f"{provider}:{event.after_sha}:{event.event_type}",
        timestamp=timestamp,
        now=time.time(),
    ):
        raise HTTPException(status_code=409, detail="Replay detected or delivery expired")

    return {
        "accepted": True,
        "event": {
            "provider": event.provider,
            "event_type": event.event_type,
            "delivery_id": event.delivery_id,
            "full_name": event.full_name,
            "ref": event.ref,
            "before_sha": event.before_sha,
            "after_sha": event.after_sha,
            "action": event.action,
            "pr_number": event.pr_number,
        },
    }

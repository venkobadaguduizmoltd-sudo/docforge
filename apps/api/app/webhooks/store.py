"""In-memory webhook registration store."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class WebhookRegistration:
    id: str
    provider: str
    full_name: str
    secret: str
    events: list[str] = field(default_factory=lambda: ["push", "pull_request"])
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "full_name": self.full_name,
            "events": self.events,
            "active": self.active,
            "created_at": self.created_at,
            "has_secret": bool(self.secret),
            "metadata": self.metadata,
        }


class WebhookStore:
    def __init__(self) -> None:
        self._items: dict[str, WebhookRegistration] = {}

    def register(
        self,
        *,
        provider: str,
        full_name: str,
        secret: str | None = None,
        events: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WebhookRegistration:
        item = WebhookRegistration(
            id=str(uuid.uuid4()),
            provider=provider.lower().strip(),
            full_name=full_name,
            secret=secret or secrets.token_urlsafe(24),
            events=events or ["push", "pull_request"],
            metadata=metadata or {},
        )
        self._items[item.id] = item
        return item

    def get(self, webhook_id: str) -> WebhookRegistration | None:
        return self._items.get(webhook_id)

    def list_for(self, provider: str | None = None) -> list[WebhookRegistration]:
        items = list(self._items.values())
        if provider:
            items = [i for i in items if i.provider == provider.lower()]
        return items

    def find_by_repo(self, provider: str, full_name: str) -> WebhookRegistration | None:
        for item in self._items.values():
            if item.provider == provider.lower() and item.full_name == full_name and item.active:
                return item
        return None


webhook_store = WebhookStore()

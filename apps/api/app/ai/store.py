"""In-memory AI provider registry for CI/dev (Postgres via Alembic for compose)."""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.ai.encryption import decrypt_secret, encrypt_secret, has_secret


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class ProviderRecord:
    id: str
    name: str
    adapter_type: str
    kind: str  # model | agent
    base_url: str | None = None
    default_model: str | None = None
    config_json: dict[str, Any] = field(default_factory=dict)
    encrypted_api_key: dict[str, Any] | None = None
    enabled: bool = True
    priority: int = 100
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "adapter_type": self.adapter_type,
            "kind": self.kind,
            "base_url": self.base_url,
            "default_model": self.default_model,
            "config_json": copy.deepcopy(self.config_json),
            "has_api_key": has_secret(self.encrypted_api_key),
            "enabled": self.enabled,
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def decrypted_api_key(self) -> str | None:
        return decrypt_secret(self.encrypted_api_key)


@dataclass
class ProviderPolicyRecord:
    id: str = "default"
    primary_provider_id: str | None = None
    fallback_provider_ids: list[str] = field(default_factory=list)
    # Budget basics (tokens / USD estimates — opaque counters for Phase 3)
    budget_daily_tokens: int | None = None
    budget_monthly_tokens: int | None = None
    tokens_used_today: int = 0
    tokens_used_month: int = 0
    allow_paid_providers: bool = False
    updated_at: str = field(default_factory=_now)

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "primary_provider_id": self.primary_provider_id,
            "fallback_provider_ids": list(self.fallback_provider_ids),
            "budget_daily_tokens": self.budget_daily_tokens,
            "budget_monthly_tokens": self.budget_monthly_tokens,
            "tokens_used_today": self.tokens_used_today,
            "tokens_used_month": self.tokens_used_month,
            "allow_paid_providers": self.allow_paid_providers,
            "updated_at": self.updated_at,
        }


_PROVIDERS: dict[str, ProviderRecord] = {}
_POLICY = ProviderPolicyRecord()


def clear_providers() -> None:
    _PROVIDERS.clear()
    global _POLICY
    _POLICY = ProviderPolicyRecord()


def seed_default_providers() -> None:
    """Idempotent seed: mock + openai_compatible stubs."""
    if _PROVIDERS:
        return
    mock = create_provider(
        name="Mock (CI)",
        adapter_type="mock",
        kind="model",
        default_model="mock-model",
        enabled=True,
        priority=0,
    )
    create_provider(
        name="Ollama (OpenAI-compatible)",
        adapter_type="openai_compatible",
        kind="model",
        base_url="http://localhost:11434",
        default_model="llama3.2",
        api_key="ollama",
        enabled=True,
        priority=10,
    )
    create_provider(
        name="OpenAI",
        adapter_type="openai",
        kind="model",
        base_url="https://api.openai.com",
        default_model="gpt-4o-mini",
        enabled=False,
        priority=20,
    )
    create_provider(
        name="Anthropic",
        adapter_type="anthropic",
        kind="model",
        base_url="https://api.anthropic.com",
        default_model="claude-3-5-sonnet-20241022",
        enabled=False,
        priority=30,
    )
    create_provider(
        name="Azure OpenAI",
        adapter_type="azure_openai",
        kind="model",
        enabled=False,
        priority=40,
    )
    create_provider(
        name="Gemini",
        adapter_type="gemini",
        kind="model",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-1.5-flash",
        enabled=False,
        priority=50,
    )
    create_provider(
        name="Bedrock",
        adapter_type="bedrock",
        kind="model",
        enabled=False,
        priority=60,
    )
    create_provider(
        name="Cursor CLI (agent)",
        adapter_type="cursor_cli",
        kind="agent",
        enabled=False,
        priority=70,
        config_json={"use_docker": True},
    )
    policy = get_policy()
    policy.primary_provider_id = mock.id
    policy.fallback_provider_ids = []
    save_policy(policy)


def list_providers() -> list[ProviderRecord]:
    return sorted(_PROVIDERS.values(), key=lambda p: (p.priority, p.name))


def get_provider(provider_id: str) -> ProviderRecord | None:
    return _PROVIDERS.get(provider_id)


def create_provider(
    *,
    name: str,
    adapter_type: str,
    kind: str = "model",
    base_url: str | None = None,
    default_model: str | None = None,
    config_json: dict[str, Any] | None = None,
    api_key: str | None = None,
    enabled: bool = True,
    priority: int = 100,
    provider_id: str | None = None,
) -> ProviderRecord:
    pid = provider_id or str(uuid.uuid4())
    record = ProviderRecord(
        id=pid,
        name=name,
        adapter_type=adapter_type,
        kind=kind,
        base_url=base_url,
        default_model=default_model,
        config_json=config_json or {},
        encrypted_api_key=encrypt_secret(api_key) if api_key else None,
        enabled=enabled,
        priority=priority,
    )
    _PROVIDERS[pid] = record
    return record


def update_provider(provider_id: str, **fields: Any) -> ProviderRecord:
    record = _PROVIDERS.get(provider_id)
    if record is None:
        raise KeyError(provider_id)
    if "name" in fields and fields["name"] is not None:
        record.name = fields["name"]
    if "adapter_type" in fields and fields["adapter_type"] is not None:
        record.adapter_type = fields["adapter_type"]
    if "kind" in fields and fields["kind"] is not None:
        record.kind = fields["kind"]
    if "base_url" in fields:
        record.base_url = fields["base_url"]
    if "default_model" in fields:
        record.default_model = fields["default_model"]
    if "config_json" in fields and fields["config_json"] is not None:
        record.config_json = fields["config_json"]
    if "enabled" in fields and fields["enabled"] is not None:
        record.enabled = fields["enabled"]
    if "priority" in fields and fields["priority"] is not None:
        record.priority = fields["priority"]
    if "api_key" in fields:
        api_key = fields["api_key"]
        if api_key:
            record.encrypted_api_key = encrypt_secret(api_key)
        elif api_key == "":
            record.encrypted_api_key = None
    record.updated_at = _now()
    return record


def delete_provider(provider_id: str) -> None:
    if provider_id not in _PROVIDERS:
        raise KeyError(provider_id)
    del _PROVIDERS[provider_id]
    policy = get_policy()
    if policy.primary_provider_id == provider_id:
        policy.primary_provider_id = None
    policy.fallback_provider_ids = [x for x in policy.fallback_provider_ids if x != provider_id]
    save_policy(policy)


def get_policy() -> ProviderPolicyRecord:
    return _POLICY


def save_policy(policy: ProviderPolicyRecord) -> ProviderPolicyRecord:
    global _POLICY
    policy.updated_at = _now()
    _POLICY = policy
    return _POLICY

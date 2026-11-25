"""Build DocGenProvider instances from stored records / settings."""

from __future__ import annotations

from app.ai.adapters import ADAPTER_TYPES
from app.ai.adapters.anthropic import AnthropicProvider
from app.ai.adapters.azure_openai import AzureOpenAIProvider
from app.ai.adapters.bedrock import BedrockProvider
from app.ai.adapters.cursor_cli import CursorCLIProvider
from app.ai.adapters.gemini import GeminiProvider
from app.ai.adapters.mock import MockProvider
from app.ai.adapters.openai import OpenAIProvider
from app.ai.adapters.openai_compatible import OpenAICompatibleProvider
from app.ai.errors import ProviderError, ProviderErrorCode
from app.ai.protocol import DocGenProvider
from app.ai.store import ProviderRecord, get_provider, get_policy, list_providers, seed_default_providers
from app.ai.types import ProviderKind
from app.core.config import get_settings


def build_provider(record: ProviderRecord) -> DocGenProvider:
    api_key = record.decrypted_api_key() or ""
    cfg = record.config_json or {}
    adapter = record.adapter_type
    kwargs: dict = {
        "name": record.name,
        "api_key": api_key,
    }
    if record.default_model:
        kwargs["model"] = record.default_model
    if record.base_url:
        kwargs["base_url"] = record.base_url
    if "timeout_seconds" in cfg:
        kwargs["timeout_seconds"] = float(cfg["timeout_seconds"])

    if adapter in {"mock"}:
        return MockProvider(models=[record.default_model or "mock-model"])
    if adapter in {"openai_compatible", "ollama"}:
        settings = get_settings()
        return OpenAICompatibleProvider(
            base_url=record.base_url or settings.ollama_base_url,
            api_key=api_key or settings.llm_api_key,
            model=record.default_model or settings.llm_model,
            name=record.name,
            timeout_seconds=float(cfg.get("timeout_seconds", 120)),
        )
    if adapter == "openai":
        return OpenAIProvider(**kwargs)
    if adapter == "anthropic":
        return AnthropicProvider(**kwargs)
    if adapter == "azure_openai":
        if "api_version" in cfg:
            kwargs["api_version"] = cfg["api_version"]
        if not record.base_url:
            raise ProviderError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                "Azure OpenAI requires base_url (resource endpoint)",
            )
        return AzureOpenAIProvider(**kwargs)
    if adapter in {"gemini", "vertex"}:
        if cfg.get("project"):
            kwargs["project"] = cfg["project"]
        if cfg.get("location"):
            kwargs["location"] = cfg["location"]
        return GeminiProvider(**kwargs)
    if adapter == "bedrock":
        if cfg.get("region"):
            kwargs["region"] = cfg["region"]
        return BedrockProvider(**kwargs)
    if adapter == "cursor_cli":
        return CursorCLIProvider(
            api_key=api_key,
            model=record.default_model,
            name=record.name,
            timeout_seconds=float(cfg.get("timeout_seconds", 180)),
            docker_image=str(cfg.get("docker_image", "cursor-agent:local")),
            use_docker=cfg.get("use_docker"),
        )
    raise ProviderError(
        ProviderErrorCode.PROVIDER_UNAVAILABLE,
        f"Unknown adapter type: {adapter}",
        details={"known": sorted(ADAPTER_TYPES)},
    )


def provider_from_settings() -> DocGenProvider:
    """Legacy Phase 1 env-based selection (mock | openai_compatible)."""
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider in {"mock", "fixture", "test"}:
        return MockProvider()
    return OpenAICompatibleProvider(
        base_url=settings.ollama_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        name="openai_compatible",
    )


def resolve_provider(provider_id: str | None = None) -> DocGenProvider:
    seed_default_providers()
    if provider_id:
        record = get_provider(provider_id)
        if record is None:
            raise ProviderError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                f"Provider not found: {provider_id}",
            )
        if not record.enabled:
            raise ProviderError(
                ProviderErrorCode.POLICY_BLOCKED,
                f"Provider disabled: {provider_id}",
            )
        return build_provider(record)

    policy = get_policy()
    if policy.primary_provider_id:
        record = get_provider(policy.primary_provider_id)
        if record and record.enabled:
            return build_provider(record)

    # Fall back to env settings when store primary missing.
    return provider_from_settings()


def resolve_provider_chain() -> list[tuple[str, DocGenProvider]]:
    """Primary then fallbacks for routing."""
    seed_default_providers()
    policy = get_policy()
    chain: list[tuple[str, DocGenProvider]] = []
    seen: set[str] = set()
    ordered_ids = []
    if policy.primary_provider_id:
        ordered_ids.append(policy.primary_provider_id)
    ordered_ids.extend(policy.fallback_provider_ids)
    for pid in ordered_ids:
        if pid in seen:
            continue
        seen.add(pid)
        record = get_provider(pid)
        if record is None or not record.enabled:
            continue
        if record.kind == ProviderKind.AGENT.value:
            # Agents skip retrieval; still valid for generation when selected.
            pass
        chain.append((pid, build_provider(record)))
    if not chain:
        chain.append(("settings", provider_from_settings()))
    return chain


def list_adapter_catalog() -> list[dict]:
    return [
        {"adapter_type": "mock", "kind": "model", "requires_key": False},
        {"adapter_type": "openai_compatible", "kind": "model", "requires_key": False},
        {"adapter_type": "openai", "kind": "model", "requires_key": True},
        {"adapter_type": "anthropic", "kind": "model", "requires_key": True},
        {"adapter_type": "azure_openai", "kind": "model", "requires_key": True},
        {"adapter_type": "gemini", "kind": "model", "requires_key": True},
        {"adapter_type": "bedrock", "kind": "model", "requires_key": True},
        {"adapter_type": "cursor_cli", "kind": "agent", "requires_key": True},
    ]


def ensure_seeded() -> list[ProviderRecord]:
    seed_default_providers()
    return list_providers()

"""Admin provider store + schema guarantees (no secrets in public dict)."""

from __future__ import annotations

import pytest

from app.ai.errors import ProviderError, ProviderErrorCode
from app.ai.routing import check_budget, complete_with_routing
from app.ai.store import (
    clear_providers,
    create_provider,
    get_policy,
    list_providers,
    save_policy,
    seed_default_providers,
    update_provider,
)
from app.ai.types import CompleteRequest
from app.schemas.providers import ProviderOut


@pytest.fixture(autouse=True)
def _clean_store() -> None:
    clear_providers()
    yield
    clear_providers()


def test_seed_and_public_dict_hides_secrets() -> None:
    seed_default_providers()
    providers = list_providers()
    assert len(providers) >= 5
    keyed = create_provider(
        name="Secretive",
        adapter_type="openai",
        api_key="sk-super-secret",
    )
    public = keyed.public_dict()
    blob = str(public)
    assert "sk-super-secret" not in blob
    assert "encrypted_api_key" not in public
    assert public["has_api_key"] is True
    out = ProviderOut(**public)
    dumped = out.model_dump()
    assert "api_key" not in dumped
    assert dumped["has_api_key"] is True


def test_update_rotates_key_without_echo() -> None:
    record = create_provider(name="P", adapter_type="mock", api_key="old")
    update_provider(record.id, api_key="new-secret")
    public = record.public_dict()
    assert "new-secret" not in str(public)
    assert record.decrypted_api_key() == "new-secret"


@pytest.mark.asyncio
async def test_budget_policy_blocked() -> None:
    seed_default_providers()
    policy = get_policy()
    policy.budget_daily_tokens = 1
    policy.tokens_used_today = 1
    save_policy(policy)
    with pytest.raises(ProviderError) as exc:
        check_budget()
    assert exc.value.code == ProviderErrorCode.POLICY_BLOCKED


@pytest.mark.asyncio
async def test_routing_uses_mock_primary() -> None:
    seed_default_providers()
    result = await complete_with_routing(
        CompleteRequest(system="s", user="section_id=intro", response_json=True)
    )
    assert "summary" in result.text or result.text.startswith("{")

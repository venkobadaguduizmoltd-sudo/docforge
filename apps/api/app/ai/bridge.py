"""Bridge DocGenProvider → legacy LLMClient.complete_json interface."""

from __future__ import annotations

import json
from typing import Any

from app.ai.adapters.openai_compatible import parse_json_content
from app.ai.factory import resolve_provider
from app.ai.protocol import DocGenProvider
from app.ai.routing import complete_with_provider, complete_with_routing
from app.ai.types import CompleteRequest


class ProviderLLMClient:
    """Adapter so generation code can keep calling complete_json()."""

    def __init__(self, provider: DocGenProvider | None = None, *, use_routing: bool = True) -> None:
        self._provider = provider
        self._use_routing = use_routing

    async def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        request = CompleteRequest(system=system, user=user, response_json=True)
        if self._provider is not None:
            response = await complete_with_provider(self._provider, request)
        elif self._use_routing:
            response = await complete_with_routing(request)
        else:
            response = await complete_with_provider(resolve_provider(), request)
        if isinstance(response.text, dict):  # pragma: no cover
            return response.text
        try:
            return parse_json_content(response.text)
        except Exception:
            # Mock / providers may already return JSON text; last-chance parse.
            return json.loads(response.text)


def get_provider_llm_client(*, provider_id: str | None = None) -> ProviderLLMClient:
    if provider_id:
        return ProviderLLMClient(resolve_provider(provider_id), use_routing=False)
    return ProviderLLMClient(use_routing=True)

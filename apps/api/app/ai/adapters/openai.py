"""OpenAI chat completions adapter (optional API key)."""

from __future__ import annotations

from app.ai.adapters.openai_compatible import OpenAICompatibleProvider
from app.ai.types import ProviderKind


class OpenAIProvider(OpenAICompatibleProvider):
    adapter_type = "openai"
    kind = ProviderKind.MODEL

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com",
        name: str = "openai",
        timeout_seconds: float = 120.0,
        **kwargs,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key or "missing",
            model=model,
            name=name,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )

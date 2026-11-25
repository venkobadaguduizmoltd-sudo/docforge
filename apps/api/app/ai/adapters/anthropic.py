"""Anthropic Messages API adapter (optional API key; httpx only)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.ai.adapters.openai_compatible import parse_json_content
from app.ai.errors import ProviderError, ProviderErrorCode
from app.ai.http_errors import map_transport_error, raise_for_response
from app.ai.protocol import DocGenProvider
from app.ai.types import (
    CompleteRequest,
    CompleteResponse,
    ModelInfo,
    ProviderKind,
    TestResult,
)


class AnthropicProvider(DocGenProvider):
    adapter_type = "anthropic"
    kind = ProviderKind.MODEL

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = "claude-3-5-sonnet-20241022",
        base_url: str = "https://api.anthropic.com",
        name: str = "anthropic",
        timeout_seconds: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.default_model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = client
        self._owns = client is None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._client

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key or "missing",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def complete(self, request: CompleteRequest) -> CompleteResponse:
        client = await self._http()
        model = request.model or self.default_model
        timeout = request.timeout_seconds or self.timeout_seconds
        user_content = request.user
        if request.response_json:
            user_content = user_content + "\nRespond with JSON only."
        body: dict[str, Any] = {
            "model": model,
            "system": request.system,
            "messages": [{"role": "user", "content": user_content}],
            "max_tokens": request.max_tokens or 4096,
            "temperature": request.temperature,
        }
        try:
            response = await client.post(
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json=body,
                timeout=timeout,
            )
            raise_for_response(response)
            data = response.json()
            blocks = data.get("content") or []
            text_parts = [
                b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
            ]
            content = "".join(text_parts)
            if request.response_json:
                parse_json_content(content)
            return CompleteResponse(
                text=content,
                model=data.get("model") or model,
                usage=data.get("usage") or {},
                raw=data,
            )
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise map_transport_error(exc) from exc

    async def list_models(self) -> list[ModelInfo]:
        # Anthropic list-models is versioned; expose configured default when unauthenticated.
        if not self.api_key:
            return [ModelInfo(id=self.default_model, name=self.default_model, owned_by="anthropic")]
        client = await self._http()
        try:
            response = await client.get(
                f"{self.base_url}/v1/models",
                headers=self._headers(),
                timeout=30.0,
            )
            if response.status_code >= 400:
                return [ModelInfo(id=self.default_model, name=self.default_model, owned_by="anthropic")]
            data = response.json()
            items = data.get("data") or []
            return [
                ModelInfo(id=str(item.get("id")), name=str(item.get("display_name") or item.get("id")))
                for item in items
                if isinstance(item, dict) and item.get("id")
            ]
        except Exception:  # noqa: BLE001
            return [ModelInfo(id=self.default_model, name=self.default_model, owned_by="anthropic")]

    async def test_connection(self) -> TestResult:
        started = time.perf_counter()
        if not self.api_key:
            return TestResult(
                ok=False,
                latency_ms=(time.perf_counter() - started) * 1000,
                message="API key not configured",
            )
        try:
            models = await self.list_models()
            return TestResult(
                ok=True,
                latency_ms=(time.perf_counter() - started) * 1000,
                message="Connection ok",
                models_sample=[m.id for m in models[:5]],
            )
        except ProviderError as exc:
            return TestResult(
                ok=False,
                latency_ms=(time.perf_counter() - started) * 1000,
                message=exc.message,
            )

    async def cancel(self, handle: Any | None = None) -> None:
        if self._client is not None and self._owns:
            await self._client.aclose()
            self._client = None

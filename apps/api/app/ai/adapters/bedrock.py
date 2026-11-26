"""AWS Bedrock Runtime adapter (optional; SigV4 via pre-signed headers or bearer).

Uses httpx against the Bedrock Runtime invoke endpoint. Callers may supply a
short-lived bearer token in api_key, or leave unset — the app works without
Bedrock credentials (test_connection reports not configured).
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import quote

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


class BedrockProvider(DocGenProvider):
    adapter_type = "bedrock"
    kind = ProviderKind.MODEL

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = "anthropic.claude-3-haiku-20240307-v1:0",
        region: str = "us-east-1",
        base_url: str | None = None,
        name: str = "bedrock",
        timeout_seconds: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.default_model = model
        self.region = region
        self.base_url = (base_url or f"https://bedrock-runtime.{region}.amazonaws.com").rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = client
        self._owns = client is None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._client

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            # Supports Bedrock bearer tokens / gateway proxies; raw AWS SigV4
            # signing is out of scope for Phase 3 (optional provider).
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def complete(self, request: CompleteRequest) -> CompleteResponse:
        if not self.api_key:
            raise ProviderError(
                ProviderErrorCode.AUTH_FAILED,
                "Bedrock API key / bearer token not configured",
            )
        client = await self._http()
        model = request.model or self.default_model
        timeout = request.timeout_seconds or self.timeout_seconds
        prompt = f"{request.system}\n\n{request.user}"
        if request.response_json:
            prompt += "\nRespond with JSON only."
        # Anthropic-on-Bedrock messages-v1 body shape (common default).
        body: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": request.max_tokens or 4096,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        url = f"{self.base_url}/model/{quote(model, safe='')}/invoke"
        try:
            response = await client.post(
                url,
                headers=self._headers(),
                content=json.dumps(body),
                timeout=timeout,
            )
            raise_for_response(response)
            data = response.json()
            content_blocks = data.get("content") or []
            if content_blocks and isinstance(content_blocks, list):
                content = "".join(
                    b.get("text", "") for b in content_blocks if isinstance(b, dict)
                )
            else:
                content = data.get("completion") or data.get("outputText") or ""
            if request.response_json:
                parse_json_content(content)
            return CompleteResponse(text=content, model=model, usage={}, raw=data)
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise map_transport_error(exc) from exc

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id=self.default_model, name=self.default_model, owned_by="aws")]

    async def test_connection(self) -> TestResult:
        started = time.perf_counter()
        if not self.api_key:
            return TestResult(
                ok=False,
                latency_ms=(time.perf_counter() - started) * 1000,
                message="Bedrock credentials not configured (optional)",
            )
        return TestResult(
            ok=True,
            latency_ms=(time.perf_counter() - started) * 1000,
            message="Bearer configured (invoke not probed)",
            models_sample=[self.default_model],
        )

    async def cancel(self, handle: Any | None = None) -> None:
        if self._client is not None and self._owns:
            await self._client.aclose()
            self._client = None

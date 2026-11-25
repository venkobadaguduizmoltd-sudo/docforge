"""Google Gemini / Vertex AI generateContent adapter (optional keys; httpx)."""

from __future__ import annotations

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


class GeminiProvider(DocGenProvider):
    adapter_type = "gemini"
    kind = ProviderKind.MODEL

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = "gemini-1.5-flash",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        name: str = "gemini",
        timeout_seconds: float = 120.0,
        # Vertex: set project/location and use vertex base_url style
        project: str | None = None,
        location: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.default_model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.project = project
        self.location = location
        self._client = client
        self._owns = client is None
        if project and location:
            self.adapter_type = "vertex"

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._client

    def _generate_url(self, model: str) -> str:
        if self.project and self.location:
            # Vertex AI OpenAPI-ish path; caller supplies OAuth token as api_key.
            return (
                f"{self.base_url}/projects/{quote(self.project)}/locations/{quote(self.location)}"
                f"/publishers/google/models/{quote(model)}:generateContent"
            )
        return f"{self.base_url}/models/{quote(model)}:generateContent"

    async def complete(self, request: CompleteRequest) -> CompleteResponse:
        client = await self._http()
        model = request.model or self.default_model
        timeout = request.timeout_seconds or self.timeout_seconds
        prompt = f"{request.system}\n\n{request.user}"
        if request.response_json:
            prompt += "\nRespond with JSON only."
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": request.temperature,
            },
        }
        if request.max_tokens is not None:
            body["generationConfig"]["maxOutputTokens"] = request.max_tokens
        if request.response_json:
            body["generationConfig"]["responseMimeType"] = "application/json"

        headers: dict[str, str] = {"Content-Type": "application/json"}
        params: dict[str, str] = {}
        if self.project and self.location:
            headers["Authorization"] = f"Bearer {self.api_key or 'missing'}"
        else:
            params["key"] = self.api_key or "missing"

        try:
            response = await client.post(
                self._generate_url(model),
                headers=headers,
                params=params,
                json=body,
                timeout=timeout,
            )
            raise_for_response(response)
            data = response.json()
            candidates = data.get("candidates") or []
            parts = (
                (((candidates[0] or {}).get("content") or {}).get("parts") or [])
                if candidates
                else []
            )
            content = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            if request.response_json:
                parse_json_content(content)
            return CompleteResponse(
                text=content,
                model=model,
                usage=data.get("usageMetadata") or {},
                raw=data,
            )
        except ProviderError:
            raise
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                ProviderErrorCode.INVALID_OUTPUT,
                "Unexpected Gemini response shape",
                details={"error": str(exc)},
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise map_transport_error(exc) from exc

    async def list_models(self) -> list[ModelInfo]:
        if self.project and self.location:
            return [ModelInfo(id=self.default_model, name=self.default_model, owned_by="vertex")]
        if not self.api_key:
            return [ModelInfo(id=self.default_model, name=self.default_model, owned_by="google")]
        client = await self._http()
        try:
            response = await client.get(
                f"{self.base_url}/models",
                params={"key": self.api_key},
                timeout=30.0,
            )
            if response.status_code >= 400:
                return [ModelInfo(id=self.default_model, name=self.default_model, owned_by="google")]
            data = response.json()
            items = data.get("models") or []
            out: list[ModelInfo] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                mid = str(item.get("name") or "").removeprefix("models/")
                if mid:
                    out.append(ModelInfo(id=mid, name=item.get("displayName") or mid, owned_by="google"))
            return out or [ModelInfo(id=self.default_model, name=self.default_model)]
        except Exception:  # noqa: BLE001
            return [ModelInfo(id=self.default_model, name=self.default_model, owned_by="google")]

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

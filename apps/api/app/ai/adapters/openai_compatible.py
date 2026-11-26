"""Hardened OpenAI-compatible chat client (default path for Ollama)."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

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


def parse_json_content(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        lines = [ln for ln in lines if not ln.startswith("```")]
        content = "\n".join(lines)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderError(
            ProviderErrorCode.INVALID_OUTPUT,
            "Provider returned non-JSON content",
            details={"error": str(exc), "snippet": content[:300]},
        ) from exc
    if not isinstance(data, dict):
        raise ProviderError(
            ProviderErrorCode.INVALID_OUTPUT,
            "Provider JSON was not an object",
            details={"type": type(data).__name__},
        )
    return data


class OpenAICompatibleProvider(DocGenProvider):
    """Chat completions against OpenAI-compatible endpoints (Ollama, LiteLLM, etc.)."""

    adapter_type = "openai_compatible"
    kind = ProviderKind.MODEL

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "ollama",
        model: str = "llama3.2",
        name: str = "openai_compatible",
        timeout_seconds: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = model
        self.timeout_seconds = timeout_seconds
        self._client = client
        self._owns = client is None
        self._active: httpx.Response | None = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._client

    async def aclose(self) -> None:
        if self._owns and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def complete(self, request: CompleteRequest) -> CompleteResponse:
        client = await self._http()
        model = request.model or self.default_model
        timeout = request.timeout_seconds or self.timeout_seconds
        url = f"{self.base_url}/v1/chat/completions"
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.response_json:
            body["response_format"] = {"type": "json_object"}

        try:
            response = await client.post(
                url,
                headers=self._headers(),
                json=body,
                timeout=timeout,
            )
            self._active = response
            # Some Ollama builds ignore / reject response_format — retry without it.
            if response.status_code >= 400 and request.response_json:
                retry_body = {k: v for k, v in body.items() if k != "response_format"}
                retry_body["messages"] = [
                    {"role": "system", "content": request.system},
                    {
                        "role": "user",
                        "content": request.user + "\nRespond with JSON only.",
                    },
                ]
                response = await client.post(
                    url,
                    headers=self._headers(),
                    json=retry_body,
                    timeout=timeout,
                )
                self._active = response
            raise_for_response(response)
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if request.response_json:
                parse_json_content(content)  # validate shape early
            usage = data.get("usage") or {}
            return CompleteResponse(
                text=content,
                model=data.get("model") or model,
                usage=usage if isinstance(usage, dict) else {},
                raw=data if isinstance(data, dict) else {},
            )
        except ProviderError:
            raise
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                ProviderErrorCode.INVALID_OUTPUT,
                "Unexpected provider response shape",
                details={"error": str(exc)},
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise map_transport_error(exc) from exc
        finally:
            self._active = None

    async def list_models(self) -> list[ModelInfo]:
        client = await self._http()
        url = f"{self.base_url}/v1/models"
        try:
            response = await client.get(url, headers=self._headers(), timeout=30.0)
            raise_for_response(response)
            data = response.json()
            items = data.get("data") if isinstance(data, dict) else None
            if not isinstance(items, list):
                # Ollama native fallback
                tags = await client.get(f"{self.base_url}/api/tags", timeout=30.0)
                if tags.status_code < 400:
                    payload = tags.json()
                    models = payload.get("models") or []
                    return [
                        ModelInfo(id=m.get("name") or m.get("model") or "unknown", name=m.get("name"))
                        for m in models
                        if isinstance(m, dict)
                    ]
                return [ModelInfo(id=self.default_model, name=self.default_model)]
            return [
                ModelInfo(
                    id=str(item.get("id")),
                    name=str(item.get("id")),
                    owned_by=item.get("owned_by"),
                )
                for item in items
                if isinstance(item, dict) and item.get("id")
            ]
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise map_transport_error(exc) from exc

    async def test_connection(self) -> TestResult:
        started = time.perf_counter()
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
        # httpx requests are not individually cancellable without Abort; best-effort close.
        if self._client is not None and self._owns:
            await self._client.aclose()
            self._client = None

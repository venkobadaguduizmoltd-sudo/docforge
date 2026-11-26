"""Azure OpenAI adapter (optional keys; deployments via base_url)."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.adapters.openai_compatible import OpenAICompatibleProvider, parse_json_content
from app.ai.errors import ProviderError, ProviderErrorCode
from app.ai.http_errors import map_transport_error, raise_for_response
from app.ai.types import CompleteRequest, CompleteResponse, ProviderKind


class AzureOpenAIProvider(OpenAICompatibleProvider):
    """Uses Azure deployment URL pattern with api-key header."""

    adapter_type = "azure_openai"
    kind = ProviderKind.MODEL

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        api_version: str = "2024-08-01-preview",
        name: str = "azure_openai",
        timeout_seconds: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key or "missing",
            model=model,
            name=name,
            timeout_seconds=timeout_seconds,
            client=client,
        )
        self.api_version = api_version

    def _headers(self) -> dict[str, str]:
        return {"api-key": self.api_key, "Content-Type": "application/json"}

    async def complete(self, request: CompleteRequest) -> CompleteResponse:
        client = await self._http()
        deployment = request.model or self.default_model
        timeout = request.timeout_seconds or self.timeout_seconds
        url = (
            f"{self.base_url.rstrip('/')}/openai/deployments/{deployment}"
            f"/chat/completions?api-version={self.api_version}"
        )
        body: dict[str, Any] = {
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
            response = await client.post(url, headers=self._headers(), json=body, timeout=timeout)
            raise_for_response(response)
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if request.response_json:
                parse_json_content(content)
            return CompleteResponse(
                text=content,
                model=deployment,
                usage=data.get("usage") or {},
                raw=data,
            )
        except ProviderError:
            raise
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                ProviderErrorCode.INVALID_OUTPUT,
                "Unexpected Azure OpenAI response shape",
                details={"error": str(exc)},
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise map_transport_error(exc) from exc

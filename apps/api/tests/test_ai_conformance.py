"""Provider conformance suite: schema, timeouts, error mapping, cancel.

Live network tests are gated by DOCFORGE_LIVE_PROVIDER_TESTS=1.
"""

from __future__ import annotations

import asyncio
import json
import os

import httpx
import pytest

from app.ai.adapters.cursor_cli import (
    FORBIDDEN_FLAGS,
    build_cursor_argv,
    map_cursor_exit,
)
from app.ai.adapters.mock import MockProvider
from app.ai.adapters.openai_compatible import OpenAICompatibleProvider, parse_json_content
from app.ai.errors import ProviderError, ProviderErrorCode
from app.ai.http_errors import map_http_status, map_transport_error
from app.ai.types import CompleteRequest, ProviderKind


@pytest.mark.asyncio
async def test_mock_complete_json_schema() -> None:
    provider = MockProvider()
    result = await provider.complete(
        CompleteRequest(system="sys", user="section_id=overview please", response_json=True)
    )
    data = json.loads(result.text)
    assert "summary" in data and "bullets" in data
    assert isinstance(data["bullets"], list)


@pytest.mark.asyncio
async def test_mock_timeout() -> None:
    provider = MockProvider(delay_seconds=2.0)
    with pytest.raises(ProviderError) as exc:
        await provider.complete(
            CompleteRequest(system="s", user="u", timeout_seconds=0.05, response_json=True)
        )
    assert exc.value.code == ProviderErrorCode.TIMEOUT


@pytest.mark.asyncio
async def test_mock_error_mapping() -> None:
    for code in ProviderErrorCode:
        provider = MockProvider(fail_with=code)
        with pytest.raises(ProviderError) as exc:
            await provider.complete(CompleteRequest(system="s", user="u"))
        assert exc.value.code == code


@pytest.mark.asyncio
async def test_mock_cancel() -> None:
    provider = MockProvider(delay_seconds=5.0)

    async def _run() -> None:
        await provider.complete(CompleteRequest(system="s", user="u"))

    task = asyncio.create_task(_run())
    await asyncio.sleep(0.05)
    await provider.cancel()
    with pytest.raises(ProviderError) as exc:
        await task
    assert exc.value.code == ProviderErrorCode.TIMEOUT


def test_http_status_mapping() -> None:
    assert map_http_status(401).code == ProviderErrorCode.AUTH_FAILED
    assert map_http_status(403).code == ProviderErrorCode.AUTH_FAILED
    assert map_http_status(429).code == ProviderErrorCode.RATE_LIMITED
    assert map_http_status(503).code == ProviderErrorCode.PROVIDER_UNAVAILABLE
    assert map_http_status(400).code == ProviderErrorCode.PROVIDER_UNAVAILABLE


def test_transport_timeout_mapping() -> None:
    err = map_transport_error(httpx.ReadTimeout("slow"))
    assert err.code == ProviderErrorCode.TIMEOUT
    err2 = map_transport_error(httpx.ConnectError("down"))
    assert err2.code == ProviderErrorCode.PROVIDER_UNAVAILABLE


def test_parse_json_invalid() -> None:
    with pytest.raises(ProviderError) as exc:
        parse_json_content("not-json")
    assert exc.value.code == ProviderErrorCode.INVALID_OUTPUT


@pytest.mark.asyncio
async def test_openai_compatible_auth_and_timeout() -> None:
    base = "https://llm.test"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/chat/completions"):
            if request.headers.get("authorization") == "Bearer bad":
                return httpx.Response(401, text="nope")
            raise httpx.ReadTimeout("t", request=request)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleProvider(
            base_url=base, api_key="bad", model="m", client=client
        )
        with pytest.raises(ProviderError) as exc:
            await provider.complete(CompleteRequest(system="s", user="u", response_json=False))
        assert exc.value.code == ProviderErrorCode.AUTH_FAILED

        provider2 = OpenAICompatibleProvider(
            base_url=base, api_key="ok", model="m", client=client
        )
        with pytest.raises(ProviderError) as exc2:
            await provider2.complete(CompleteRequest(system="s", user="u", response_json=False))
        assert exc2.value.code == ProviderErrorCode.TIMEOUT


@pytest.mark.asyncio
async def test_openai_compatible_success_json() -> None:
    base = "https://llm.test"
    payload = {
        "title": "T",
        "summary": "S",
        "bullets": [],
        "code_refs": [],
        "notes": None,
        "citations": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "m",
                "choices": [{"message": {"content": json.dumps(payload)}}],
                "usage": {"total_tokens": 3},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleProvider(
            base_url=base, api_key="k", model="m", client=client
        )
        result = await provider.complete(
            CompleteRequest(system="s", user="u", response_json=True)
        )
        assert json.loads(result.text)["summary"] == "S"


def test_cursor_cli_no_force_and_error_map() -> None:
    argv = build_cursor_argv(prompt="hello", model="auto")
    for flag in FORBIDDEN_FLAGS:
        assert flag not in argv
    assert map_cursor_exit(0, "", "ok") is None
    assert map_cursor_exit(124, "timed out", "").code == ProviderErrorCode.TIMEOUT
    assert map_cursor_exit(1, "unauthorized api key", "").code == ProviderErrorCode.AUTH_FAILED
    assert map_cursor_exit(1, "rate limit exceeded", "").code == ProviderErrorCode.RATE_LIMITED
    assert map_cursor_exit(127, "not found", "").code == ProviderErrorCode.PROVIDER_UNAVAILABLE


def test_cursor_agent_kind_skips_retrieval() -> None:
    from app.ai.adapters.cursor_cli import CursorCLIProvider

    p = CursorCLIProvider(api_key="x", use_docker=False)
    assert p.kind == ProviderKind.AGENT
    assert p.skips_retrieval is True


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("DOCFORGE_LIVE_PROVIDER_TESTS", "").lower() not in {"1", "true", "yes"},
    reason="Live provider tests gated by DOCFORGE_LIVE_PROVIDER_TESTS",
)
async def test_live_openai_compatible_ollama() -> None:
    base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    provider = OpenAICompatibleProvider(base_url=base, api_key="ollama", model="llama3.2")
    result = await provider.test_connection()
    assert result.ok or result.message
    await provider.aclose()

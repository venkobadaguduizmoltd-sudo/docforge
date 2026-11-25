"""Map HTTP / transport failures to normalized ProviderError codes."""

from __future__ import annotations

import httpx

from app.ai.errors import ProviderError, ProviderErrorCode


def map_http_status(status: int, body: str = "") -> ProviderError:
    snippet = (body or "")[:500]
    if status in {401, 403}:
        return ProviderError(
            ProviderErrorCode.AUTH_FAILED,
            f"Authentication failed ({status})",
            details={"status": status, "body": snippet},
        )
    if status == 429:
        return ProviderError(
            ProviderErrorCode.RATE_LIMITED,
            "Rate limited by provider",
            retryable=True,
            details={"status": status, "body": snippet},
        )
    if status >= 500:
        return ProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            f"Provider unavailable ({status})",
            retryable=True,
            details={"status": status, "body": snippet},
        )
    return ProviderError(
        ProviderErrorCode.PROVIDER_UNAVAILABLE,
        f"Provider request failed ({status})",
        details={"status": status, "body": snippet},
    )


def map_transport_error(exc: BaseException) -> ProviderError:
    if isinstance(exc, ProviderError):
        return exc
    if isinstance(exc, httpx.TimeoutException):
        return ProviderError(
            ProviderErrorCode.TIMEOUT,
            "Provider request timed out",
            retryable=True,
            details={"type": type(exc).__name__},
        )
    if isinstance(exc, (httpx.ConnectError, httpx.NetworkError)):
        return ProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "Provider unreachable",
            retryable=True,
            details={"type": type(exc).__name__, "error": str(exc)},
        )
    if isinstance(exc, httpx.HTTPStatusError):
        body = ""
        try:
            body = exc.response.text
        except Exception:  # noqa: BLE001
            body = ""
        return map_http_status(exc.response.status_code, body)
    return ProviderError(
        ProviderErrorCode.PROVIDER_UNAVAILABLE,
        f"Provider error: {exc}",
        details={"type": type(exc).__name__},
    )


def raise_for_response(response: httpx.Response) -> None:
    if response.status_code >= 400:
        raise map_http_status(response.status_code, response.text)

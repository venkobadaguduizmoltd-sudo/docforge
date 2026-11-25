"""Provider routing, fallback, and budget basics."""

from __future__ import annotations

from typing import Any

from app.ai.errors import ProviderError, ProviderErrorCode
from app.ai.factory import resolve_provider_chain
from app.ai.protocol import DocGenProvider
from app.ai.store import get_policy, save_policy
from app.ai.types import CompleteRequest, CompleteResponse


def check_budget() -> None:
    policy = get_policy()
    if (
        policy.budget_daily_tokens is not None
        and policy.tokens_used_today >= policy.budget_daily_tokens
    ):
        raise ProviderError(
            ProviderErrorCode.POLICY_BLOCKED,
            "Daily token budget exhausted",
            details={"tokens_used_today": policy.tokens_used_today},
        )
    if (
        policy.budget_monthly_tokens is not None
        and policy.tokens_used_month >= policy.budget_monthly_tokens
    ):
        raise ProviderError(
            ProviderErrorCode.POLICY_BLOCKED,
            "Monthly token budget exhausted",
            details={"tokens_used_month": policy.tokens_used_month},
        )


def record_usage(usage: dict[str, Any] | None) -> None:
    if not usage:
        return
    tokens = int(
        usage.get("total_tokens")
        or (
            int(usage.get("prompt_tokens") or 0)
            + int(usage.get("completion_tokens") or 0)
        )
        or usage.get("input_tokens")
        or 0
    )
    if tokens <= 0:
        tokens = 1
    policy = get_policy()
    policy.tokens_used_today += tokens
    policy.tokens_used_month += tokens
    save_policy(policy)


async def complete_with_routing(request: CompleteRequest) -> CompleteResponse:
    """Try primary then fallbacks; map non-retryable auth to next only on unavailable/rate/timeout."""
    check_budget()
    chain = resolve_provider_chain()
    last_error: ProviderError | None = None
    for _pid, provider in chain:
        # Agent providers always skip retrieval.
        req = CompleteRequest(
            system=request.system,
            user=request.user,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            response_json=request.response_json,
            skip_retrieval=request.skip_retrieval or provider.skips_retrieval,
            timeout_seconds=request.timeout_seconds,
            metadata=request.metadata,
        )
        try:
            result = await provider.complete(req)
            record_usage(result.usage)
            return result
        except ProviderError as exc:
            last_error = exc
            if exc.code in {
                ProviderErrorCode.AUTH_FAILED,
                ProviderErrorCode.INVALID_OUTPUT,
                ProviderErrorCode.POLICY_BLOCKED,
            }:
                # Do not blindly fall through auth/policy failures on primary —
                # still try fallbacks for unavailable-class errors only.
                if exc.code == ProviderErrorCode.POLICY_BLOCKED:
                    raise
                continue
            if exc.code in {
                ProviderErrorCode.RATE_LIMITED,
                ProviderErrorCode.TIMEOUT,
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
            }:
                continue
            raise
    if last_error:
        raise last_error
    raise ProviderError(
        ProviderErrorCode.PROVIDER_UNAVAILABLE,
        "No providers available in routing chain",
    )


async def complete_with_provider(
    provider: DocGenProvider,
    request: CompleteRequest,
) -> CompleteResponse:
    check_budget()
    req = CompleteRequest(
        system=request.system,
        user=request.user,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        response_json=request.response_json,
        skip_retrieval=request.skip_retrieval or provider.skips_retrieval,
        timeout_seconds=request.timeout_seconds,
        metadata=request.metadata,
    )
    result = await provider.complete(req)
    record_usage(result.usage)
    return result

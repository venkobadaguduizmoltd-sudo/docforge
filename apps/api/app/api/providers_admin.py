"""Admin AI provider CRUD, test, models, and policy endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.errors import ProviderError
from app.ai.factory import build_provider, ensure_seeded, list_adapter_catalog
from app.ai.store import (
    create_provider,
    delete_provider,
    get_policy,
    get_provider,
    list_providers,
    save_policy,
    update_provider,
)
from app.models.user import User
from app.rbac.deps import require_role
from app.rbac.roles import RoleName
from app.schemas.providers import (
    ModelInfoOut,
    ModelListOut,
    ProviderCreate,
    ProviderListOut,
    ProviderOut,
    ProviderPolicyOut,
    ProviderPolicyUpdate,
    ProviderTestOut,
    ProviderUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin-providers"])


def _to_out(record) -> ProviderOut:
    data = record.public_dict()
    # Defense: strip any accidental secret fields
    data.pop("encrypted_api_key", None)
    data.pop("api_key", None)
    return ProviderOut(**data)


@router.get("/providers", response_model=ProviderListOut)
def admin_list_providers(
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> ProviderListOut:
    ensure_seeded()
    return ProviderListOut(
        providers=[_to_out(p) for p in list_providers()],
        adapters=list_adapter_catalog(),
    )


@router.post("/providers", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
def admin_create_provider(
    body: ProviderCreate,
    _user: User = Depends(require_role(RoleName.ADMIN)),
) -> ProviderOut:
    ensure_seeded()
    record = create_provider(
        name=body.name,
        adapter_type=body.adapter_type,
        kind=body.kind,
        base_url=body.base_url,
        default_model=body.default_model,
        config_json=body.config_json,
        api_key=body.api_key,
        enabled=body.enabled,
        priority=body.priority,
    )
    out = _to_out(record)
    assert "api_key" not in out.model_dump()
    return out


@router.get("/providers/{provider_id}", response_model=ProviderOut)
def admin_get_provider(
    provider_id: str,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> ProviderOut:
    ensure_seeded()
    record = get_provider(provider_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _to_out(record)


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
def admin_update_provider(
    provider_id: str,
    body: ProviderUpdate,
    _user: User = Depends(require_role(RoleName.ADMIN)),
) -> ProviderOut:
    ensure_seeded()
    if get_provider(provider_id) is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    fields = body.model_dump(exclude_unset=True)
    try:
        record = update_provider(provider_id, **fields)
    except KeyError:
        raise HTTPException(status_code=404, detail="Provider not found") from None
    return _to_out(record)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_provider(
    provider_id: str,
    _user: User = Depends(require_role(RoleName.ADMIN)),
) -> None:
    ensure_seeded()
    try:
        delete_provider(provider_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Provider not found") from None


@router.post("/providers/{provider_id}/test", response_model=ProviderTestOut)
async def admin_test_provider(
    provider_id: str,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> ProviderTestOut:
    ensure_seeded()
    record = get_provider(provider_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    try:
        provider = build_provider(record)
        result = await provider.test_connection()
        return ProviderTestOut(
            ok=result.ok,
            latency_ms=result.latency_ms,
            message=result.message,
            models_sample=result.models_sample,
        )
    except ProviderError as exc:
        return ProviderTestOut(ok=False, latency_ms=0.0, message=exc.message)


@router.get("/providers/{provider_id}/models", response_model=ModelListOut)
async def admin_list_models(
    provider_id: str,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> ModelListOut:
    ensure_seeded()
    record = get_provider(provider_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    try:
        provider = build_provider(record)
        models = await provider.list_models()
        return ModelListOut(
            models=[ModelInfoOut(id=m.id, name=m.name, owned_by=m.owned_by) for m in models]
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=exc.to_dict()) from exc


@router.get("/provider-policies", response_model=ProviderPolicyOut)
def admin_get_policy(
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> ProviderPolicyOut:
    ensure_seeded()
    return ProviderPolicyOut(**get_policy().public_dict())


@router.put("/provider-policies", response_model=ProviderPolicyOut)
def admin_put_policy(
    body: ProviderPolicyUpdate,
    _user: User = Depends(require_role(RoleName.ADMIN)),
) -> ProviderPolicyOut:
    ensure_seeded()
    policy = get_policy()
    if body.primary_provider_id is not None:
        if body.primary_provider_id and get_provider(body.primary_provider_id) is None:
            raise HTTPException(status_code=400, detail="primary_provider_id not found")
        policy.primary_provider_id = body.primary_provider_id or None
    if body.fallback_provider_ids is not None:
        for pid in body.fallback_provider_ids:
            if get_provider(pid) is None:
                raise HTTPException(status_code=400, detail=f"fallback provider not found: {pid}")
        policy.fallback_provider_ids = list(body.fallback_provider_ids)
    if "budget_daily_tokens" in body.model_fields_set:
        policy.budget_daily_tokens = body.budget_daily_tokens
    if "budget_monthly_tokens" in body.model_fields_set:
        policy.budget_monthly_tokens = body.budget_monthly_tokens
    if body.allow_paid_providers is not None:
        policy.allow_paid_providers = body.allow_paid_providers
    if body.reset_usage:
        policy.tokens_used_today = 0
        policy.tokens_used_month = 0
    save_policy(policy)
    return ProviderPolicyOut(**get_policy().public_dict())

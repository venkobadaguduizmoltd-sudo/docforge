"""Admin AI provider schemas — never include decrypted secrets."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProviderOut(BaseModel):
    id: str
    name: str
    adapter_type: str
    kind: Literal["model", "agent"]
    base_url: str | None = None
    default_model: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)
    has_api_key: bool = False
    enabled: bool = True
    priority: int = 100
    created_at: str
    updated_at: str


class ProviderListOut(BaseModel):
    providers: list[ProviderOut]
    adapters: list[dict[str, Any]] = Field(default_factory=list)


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    adapter_type: str = Field(min_length=1, max_length=64)
    kind: Literal["model", "agent"] = "model"
    base_url: str | None = None
    default_model: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)
    api_key: str | None = Field(default=None, description="Write-only; never returned")
    enabled: bool = True
    priority: int = 100


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    adapter_type: str | None = None
    kind: Literal["model", "agent"] | None = None
    base_url: str | None = None
    default_model: str | None = None
    config_json: dict[str, Any] | None = None
    api_key: str | None = Field(default=None, description="Write-only; omit to leave unchanged")
    enabled: bool | None = None
    priority: int | None = None


class ProviderTestOut(BaseModel):
    ok: bool
    latency_ms: float
    message: str
    models_sample: list[str] = Field(default_factory=list)


class ModelInfoOut(BaseModel):
    id: str
    name: str | None = None
    owned_by: str | None = None


class ModelListOut(BaseModel):
    models: list[ModelInfoOut]


class ProviderPolicyOut(BaseModel):
    id: str
    primary_provider_id: str | None = None
    fallback_provider_ids: list[str] = Field(default_factory=list)
    budget_daily_tokens: int | None = None
    budget_monthly_tokens: int | None = None
    tokens_used_today: int = 0
    tokens_used_month: int = 0
    allow_paid_providers: bool = False
    updated_at: str


class ProviderPolicyUpdate(BaseModel):
    primary_provider_id: str | None = None
    fallback_provider_ids: list[str] | None = None
    budget_daily_tokens: int | None = None
    budget_monthly_tokens: int | None = None
    allow_paid_providers: bool | None = None
    reset_usage: bool = False

"""Pydantic schemas for Phase 4 admin template studio."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

TemplateStatus = Literal["draft", "published", "deprecated"]


class TemplateOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: TemplateStatus
    source: str
    current_version_id: str | None = None
    current_version: int | None = None
    sha256: str | None = None
    immutable: bool = False
    last_test_run_ok: bool = False
    created_at: str
    updated_at: str
    spec: dict[str, Any] | None = None
    version_detail: dict[str, Any] | None = None


class TemplateListOut(BaseModel):
    templates: list[TemplateOut]


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    spec: dict[str, Any] | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class TemplateSpecPut(BaseModel):
    spec: dict[str, Any]


class TemplateYamlPut(BaseModel):
    yaml_text: str = Field(min_length=1)


class PromptTemplateRequest(BaseModel):
    description: str = Field(min_length=1)
    name: str | None = None


class CloneTemplateRequest(BaseModel):
    name: str | None = None


class TestRunRequest(BaseModel):
    provider: str = "fixture"
    full_name: str = "docforge/sample"
    ref: str = "main"


class TestRunOut(BaseModel):
    ok: bool
    job_id: str | None = None
    error: str | None = None
    template: TemplateOut


class YamlOut(BaseModel):
    yaml_text: str

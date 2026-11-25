"""Job and repository request/response schemas."""

from typing import Any

from pydantic import BaseModel, Field


class GenerateJobRequest(BaseModel):
    provider: str = Field(default="fixture", description="fixture | github | gitlab")
    full_name: str = "docforge/sample"
    ref: str = "main"
    template_slug: str = "tech-overview"
    token: str | None = None
    api_base: str | None = None


class JobOut(BaseModel):
    id: str
    job_type: str
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    commit_sha: str | None = None
    created_at: str
    updated_at: str


class JobListOut(BaseModel):
    jobs: list[JobOut]


class ListReposRequest(BaseModel):
    provider: str = "fixture"
    query: str | None = None
    token: str | None = None
    api_base: str | None = None


class ListRefsRequest(BaseModel):
    provider: str = "fixture"
    full_name: str
    token: str | None = None
    api_base: str | None = None

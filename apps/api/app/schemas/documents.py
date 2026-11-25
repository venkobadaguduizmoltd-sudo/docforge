"""Document correction / version schemas (Phase 2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CitationOut(BaseModel):
    file: str
    line: int | None = None
    end_line: int | None = None
    commit_sha: str | None = None
    symbol: str | None = None


class SectionOut(BaseModel):
    section_id: str
    content_json: dict[str, Any]
    is_locked: bool = False
    citations: list[CitationOut] = Field(default_factory=list)
    pending_suggestion: dict[str, Any] | None = None
    updated_at: str


class DocumentOut(BaseModel):
    id: str
    title: str
    status: str
    source_job_id: str | None = None
    template_slug: str
    template_sha256: str | None = None
    pinned_commit_sha: str | None = None
    sections: list[SectionOut]
    current_revision: int
    created_at: str
    updated_at: str


class SectionEditRequest(BaseModel):
    content: dict[str, Any]


class SectionRegenRequest(BaseModel):
    prompt: str | None = None


class SuggestRequest(BaseModel):
    prompt: str | None = None


class RegenAllRequest(BaseModel):
    prompt: str | None = None


class RevisionOut(BaseModel):
    revision_number: int
    note: str | None = None
    created_at: str


class RevisionDetailOut(RevisionOut):
    snapshot: dict[str, Any]


class DiffOut(BaseModel):
    document_id: str
    from_revision: int
    to_revision: int
    sections: dict[str, Any]

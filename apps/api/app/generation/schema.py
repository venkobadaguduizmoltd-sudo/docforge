"""Section content schema validation — content JSON by section_id only."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError


class Citation(BaseModel):
    """Source citation pinned to a repository commit."""

    file: str
    line: int | None = None
    end_line: int | None = None
    commit_sha: str | None = None
    symbol: str | None = None


class SectionContent(BaseModel):
    """Allowed content payload for a single section."""

    title: str | None = None
    summary: str = Field(min_length=1)
    bullets: list[str] = Field(default_factory=list)
    code_refs: list[str] = Field(default_factory=list)
    notes: str | None = None
    # Phase 2 — citations (file+line at pinned commit); content-only, not template structure
    citations: list[Citation] = Field(default_factory=list)


class DocumentContent(BaseModel):
    """Map of section_id → content. Extra section keys rejected at merge time."""

    sections: dict[str, SectionContent]


class ContentOnlyViolation(Exception):
    """Raised when generated payload tries to alter template structure."""


ALLOWED_CONTENT_KEYS = frozenset(SectionContent.model_fields.keys())


def validate_section_content(section_id: str, payload: dict[str, Any]) -> SectionContent:
    if "section_id" in payload and payload["section_id"] != section_id:
        raise ContentOnlyViolation("section_id inside content must match target section")
    # Disallow template-structure keys
    forbidden = {"sections", "theme", "layout", "template", "sha256", "version", "assets"}
    bad = forbidden.intersection(payload.keys())
    if bad:
        raise ContentOnlyViolation(f"Content must not include template keys: {sorted(bad)}")
    try:
        return SectionContent.model_validate(payload)
    except ValidationError as exc:
        raise ContentOnlyViolation(str(exc)) from exc


def validate_document_content(
    content_by_section: dict[str, dict[str, Any]],
    allowed_section_ids: set[str],
) -> dict[str, SectionContent]:
    unknown = set(content_by_section) - allowed_section_ids
    if unknown:
        raise ContentOnlyViolation(f"Unknown section ids: {sorted(unknown)}")
    missing = allowed_section_ids - set(content_by_section)
    if missing:
        raise ContentOnlyViolation(f"Missing section ids: {sorted(missing)}")
    return {
        section_id: validate_section_content(section_id, payload)
        for section_id, payload in content_by_section.items()
    }

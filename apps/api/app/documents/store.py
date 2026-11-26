"""In-process document registry (Phase 2) — mirrors Phase 1 job_store for CI/dev."""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class SectionRecord:
    section_id: str
    content_json: dict[str, Any]
    is_locked: bool = False
    citations: list[dict[str, Any]] = field(default_factory=list)
    pending_suggestion: dict[str, Any] | None = None
    updated_at: str = field(default_factory=_now)

    def content_bytes(self) -> bytes:
        """Canonical bytes for byte-identical checks across siblings."""
        import json

        return json.dumps(self.content_json, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass
class RevisionRecord:
    revision_number: int
    snapshot: dict[str, Any]  # section_id → content_json (+ lock/citation metadata)
    note: str | None = None
    created_at: str = field(default_factory=_now)


@dataclass
class DocumentRecord:
    id: str
    title: str
    status: str = "draft"
    source_job_id: str | None = None
    template_slug: str = "tech-overview"
    template_sha256: str | None = None
    pinned_commit_sha: str | None = None
    analysis: dict[str, Any] = field(default_factory=dict)
    sections: dict[str, SectionRecord] = field(default_factory=dict)
    revisions: list[RevisionRecord] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def snapshot_sections(self) -> dict[str, Any]:
        return {
            sid: {
                "content_json": copy.deepcopy(sec.content_json),
                "is_locked": sec.is_locked,
                "citations": copy.deepcopy(sec.citations),
                "pending_suggestion": copy.deepcopy(sec.pending_suggestion),
            }
            for sid, sec in self.sections.items()
        }

    def current_revision_number(self) -> int:
        if not self.revisions:
            return 0
        return self.revisions[-1].revision_number


_DOCUMENTS: dict[str, DocumentRecord] = {}


def save_document(doc: DocumentRecord) -> DocumentRecord:
    doc.updated_at = _now()
    _DOCUMENTS[doc.id] = doc
    return doc


def get_document(document_id: str) -> DocumentRecord | None:
    return _DOCUMENTS.get(document_id)


def list_documents() -> list[DocumentRecord]:
    return sorted(_DOCUMENTS.values(), key=lambda d: d.created_at, reverse=True)


def clear_documents() -> None:
    _DOCUMENTS.clear()


def new_document_id() -> str:
    return str(uuid.uuid4())

"""Document section corrections, suggestions, locks, and versioning."""

from __future__ import annotations

import copy
import json
from typing import Any

from app.documents.citations import citations_from_analysis
from app.documents.store import (
    DocumentRecord,
    RevisionRecord,
    SectionRecord,
    get_document,
    new_document_id,
    save_document,
)
from app.generation.generator import generate_section_content
from app.generation.llm import get_llm_client
from app.generation.schema import ContentOnlyViolation, validate_section_content
from app.services.templates import compute_spec_sha256, load_builtin_template


class DocumentError(Exception):
    """Domain error for document operations."""


class SectionLockedError(DocumentError):
    pass


class RevisionNotFoundError(DocumentError):
    pass


def _append_revision(doc: DocumentRecord, note: str) -> RevisionRecord:
    rev = RevisionRecord(
        revision_number=doc.current_revision_number() + 1,
        snapshot=doc.snapshot_sections(),
        note=note,
    )
    doc.revisions.append(rev)
    return rev


def _get_section(doc: DocumentRecord, section_id: str) -> SectionRecord:
    section = doc.sections.get(section_id)
    if section is None:
        raise DocumentError(f"Unknown section_id: {section_id}")
    return section


def _apply_content(
    section: SectionRecord,
    content: dict[str, Any],
    *,
    citations: list[dict[str, Any]] | None = None,
) -> None:
    validated = validate_section_content(section.section_id, content)
    dumped = validated.model_dump()
    # Prefer explicit citations arg; else keep those embedded in content
    if citations is not None:
        dumped["citations"] = citations
        section.citations = copy.deepcopy(citations)
    else:
        section.citations = copy.deepcopy(dumped.get("citations") or [])
    section.content_json = dumped
    from datetime import UTC, datetime

    section.updated_at = datetime.now(UTC).isoformat()


def create_document_from_job_result(job_result: dict[str, Any], *, job_id: str | None = None) -> DocumentRecord:
    """Materialize an editable document from a completed generate job result."""
    content = job_result.get("content") or {}
    if not content:
        raise DocumentError("Job result has no content")

    template_slug = job_result.get("template_slug") or "tech-overview"
    builtin = load_builtin_template(template_slug)
    allowed = {str(s["id"]) for s in builtin["spec"]["sections"]}
    unknown = set(content) - allowed
    if unknown:
        raise ContentOnlyViolation(f"Unknown section ids: {sorted(unknown)}")

    commit_sha = job_result.get("commit_sha")
    analysis = job_result.get("analysis") or {}
    template_sha = job_result.get("template_sha256") or builtin["sha256"]
    if compute_spec_sha256(builtin["spec"]) != template_sha and job_result.get("template_sha256"):
        # Prefer sealed value from job; still verify builtin matches local seal
        if compute_spec_sha256(builtin["spec"]) != builtin["sha256"]:
            raise DocumentError("Template checksum failed")

    doc = DocumentRecord(
        id=new_document_id(),
        title=f"{template_slug} @ {(commit_sha or 'unknown')[:8]}",
        status="ready",
        source_job_id=job_id or job_result.get("job_id"),
        template_slug=template_slug,
        template_sha256=builtin["sha256"],
        pinned_commit_sha=commit_sha,
        analysis=copy.deepcopy(analysis),
    )

    for section_id, payload in content.items():
        validated = validate_section_content(section_id, payload)
        dumped = validated.model_dump()
        cites = dumped.get("citations") or citations_from_analysis(
            analysis, commit_sha=commit_sha, section_id=section_id
        )
        dumped["citations"] = cites
        doc.sections[section_id] = SectionRecord(
            section_id=section_id,
            content_json=dumped,
            citations=copy.deepcopy(cites),
        )

    _append_revision(doc, note="initial")
    return save_document(doc)


def edit_section(
    document_id: str,
    section_id: str,
    content: dict[str, Any],
    *,
    note: str = "manual_edit",
) -> DocumentRecord:
    doc = get_document(document_id)
    if doc is None:
        raise DocumentError("Document not found")
    section = _get_section(doc, section_id)
    if section.is_locked:
        raise SectionLockedError(f"Section {section_id} is locked")
    _apply_content(section, content)
    section.pending_suggestion = None
    _append_revision(doc, note=note)
    return save_document(doc)


async def regenerate_section(
    document_id: str,
    section_id: str,
    *,
    prompt: str | None = None,
    note: str | None = None,
) -> DocumentRecord:
    doc = get_document(document_id)
    if doc is None:
        raise DocumentError("Document not found")
    section = _get_section(doc, section_id)
    if section.is_locked:
        raise SectionLockedError(f"Section {section_id} is locked")

    builtin = load_builtin_template(doc.template_slug)
    # Immutability: sealed template must still match
    if compute_spec_sha256(builtin["spec"]) != builtin["sha256"]:
        raise DocumentError("Template checksum failed")
    if doc.template_sha256 and doc.template_sha256 != builtin["sha256"]:
        raise DocumentError("Document template seal does not match builtin")

    section_meta = next(
        (s for s in builtin["spec"]["sections"] if str(s["id"]) == section_id),
        None,
    )
    if section_meta is None:
        raise DocumentError(f"Section {section_id} not in template")

    # Sibling fingerprint before mutation
    before = {sid: sec.content_bytes() for sid, sec in doc.sections.items()}

    llm = get_llm_client()
    from app.analysis.analyzer import AnalysisResult
    from app.analysis.symbols import Symbol

    analysis_dict = doc.analysis or {}
    symbols = [
        Symbol(
            name=s.get("name", ""),
            kind=s.get("kind", ""),
            path=s.get("path", ""),
            line=int(s.get("line") or 1),
        )
        for s in (analysis_dict.get("symbols") or [])
        if isinstance(s, dict)
    ]
    analysis = AnalysisResult(
        root="",
        files=list(analysis_dict.get("files") or []),
        tree=list(analysis_dict.get("files") or []),
        languages=dict(analysis_dict.get("languages") or {}),
        symbols=symbols,
        redacted_excerpts={},
        secret_findings_count=int(analysis_dict.get("secret_findings_count") or 0),
    )

    generated = await generate_section_content(
        section_id=section_id,
        section_title=str(section_meta.get("title") or section_id),
        analysis=analysis,
        llm=llm,
        follow_up_prompt=prompt,
    )
    dumped = generated.model_dump()
    cites = citations_from_analysis(
        analysis_dict, commit_sha=doc.pinned_commit_sha, section_id=section_id
    )
    dumped["citations"] = cites
    _apply_content(section, dumped, citations=cites)
    section.pending_suggestion = None
    _append_revision(doc, note=note or ("regenerate" if not prompt else "regenerate_followup"))
    save_document(doc)

    # Enforce: only this section changed
    after = {sid: sec.content_bytes() for sid, sec in doc.sections.items()}
    for sid, blob in before.items():
        if sid == section_id:
            continue
        if after.get(sid) != blob:
            raise DocumentError(f"Invariant violated: sibling section {sid} changed")
    return doc


async def regenerate_all_unlocked(document_id: str, *, prompt: str | None = None) -> DocumentRecord:
    doc = get_document(document_id)
    if doc is None:
        raise DocumentError("Document not found")
    unlocked = [sid for sid, sec in doc.sections.items() if not sec.is_locked]
    for section_id in unlocked:
        await regenerate_section(document_id, section_id, prompt=prompt, note="regenerate_unlocked")
    # Collapse per-section revisions into one logical note on the latest
    doc = get_document(document_id)
    assert doc is not None
    if doc.revisions:
        doc.revisions[-1].note = "regenerate_all_unlocked"
    return save_document(doc)


async def suggest_section(
    document_id: str,
    section_id: str,
    *,
    prompt: str | None = None,
) -> DocumentRecord:
    """Generate a pending suggestion without applying it."""
    doc = get_document(document_id)
    if doc is None:
        raise DocumentError("Document not found")
    section = _get_section(doc, section_id)
    if section.is_locked:
        raise SectionLockedError(f"Section {section_id} is locked")

    # Reuse regenerate pipeline but stash as suggestion
    builtin = load_builtin_template(doc.template_slug)
    section_meta = next(
        (s for s in builtin["spec"]["sections"] if str(s["id"]) == section_id),
        None,
    )
    if section_meta is None:
        raise DocumentError(f"Section {section_id} not in template")

    from app.analysis.analyzer import AnalysisResult
    from app.analysis.symbols import Symbol

    analysis_dict = doc.analysis or {}
    symbols = [
        Symbol(
            name=s.get("name", ""),
            kind=s.get("kind", ""),
            path=s.get("path", ""),
            line=int(s.get("line") or 1),
        )
        for s in (analysis_dict.get("symbols") or [])
        if isinstance(s, dict)
    ]
    analysis = AnalysisResult(
        root="",
        files=list(analysis_dict.get("files") or []),
        tree=list(analysis_dict.get("files") or []),
        languages=dict(analysis_dict.get("languages") or {}),
        symbols=symbols,
        redacted_excerpts={},
        secret_findings_count=int(analysis_dict.get("secret_findings_count") or 0),
    )
    llm = get_llm_client()
    generated = await generate_section_content(
        section_id=section_id,
        section_title=str(section_meta.get("title") or section_id),
        analysis=analysis,
        llm=llm,
        follow_up_prompt=prompt or "Suggest an improved version of this section.",
    )
    dumped = generated.model_dump()
    cites = citations_from_analysis(
        analysis_dict, commit_sha=doc.pinned_commit_sha, section_id=section_id
    )
    dumped["citations"] = cites
    section.pending_suggestion = {
        "proposed": dumped,
        "current": copy.deepcopy(section.content_json),
        "prompt": prompt,
    }
    # Suggestion does not create a revision until accept
    return save_document(doc)


def accept_suggestion(document_id: str, section_id: str) -> DocumentRecord:
    doc = get_document(document_id)
    if doc is None:
        raise DocumentError("Document not found")
    section = _get_section(doc, section_id)
    if section.is_locked:
        raise SectionLockedError(f"Section {section_id} is locked")
    if not section.pending_suggestion:
        raise DocumentError("No pending suggestion")
    proposed = section.pending_suggestion.get("proposed") or {}
    before = {sid: sec.content_bytes() for sid, sec in doc.sections.items()}
    _apply_content(section, proposed)
    section.pending_suggestion = None
    _append_revision(doc, note="accept_suggestion")
    save_document(doc)
    after = {sid: sec.content_bytes() for sid, sec in doc.sections.items()}
    for sid, blob in before.items():
        if sid != section_id and after.get(sid) != blob:
            raise DocumentError(f"Invariant violated: sibling section {sid} changed")
    return doc


def reject_suggestion(document_id: str, section_id: str) -> DocumentRecord:
    doc = get_document(document_id)
    if doc is None:
        raise DocumentError("Document not found")
    section = _get_section(doc, section_id)
    section.pending_suggestion = None
    return save_document(doc)


def lock_section(document_id: str, section_id: str) -> DocumentRecord:
    doc = get_document(document_id)
    if doc is None:
        raise DocumentError("Document not found")
    section = _get_section(doc, section_id)
    section.is_locked = True
    _append_revision(doc, note=f"lock:{section_id}")
    return save_document(doc)


def unlock_section(document_id: str, section_id: str) -> DocumentRecord:
    doc = get_document(document_id)
    if doc is None:
        raise DocumentError("Document not found")
    section = _get_section(doc, section_id)
    section.is_locked = False
    _append_revision(doc, note=f"unlock:{section_id}")
    return save_document(doc)


def _apply_snapshot(doc: DocumentRecord, snapshot: dict[str, Any]) -> None:
    for section_id, payload in snapshot.items():
        section = doc.sections.get(section_id)
        if section is None:
            section = SectionRecord(section_id=section_id, content_json={})
            doc.sections[section_id] = section
        section.content_json = copy.deepcopy(payload.get("content_json") or {})
        section.is_locked = bool(payload.get("is_locked", False))
        section.citations = copy.deepcopy(payload.get("citations") or [])
        section.pending_suggestion = copy.deepcopy(payload.get("pending_suggestion"))


def restore_revision(document_id: str, revision_number: int) -> DocumentRecord:
    doc = get_document(document_id)
    if doc is None:
        raise DocumentError("Document not found")
    match = next((r for r in doc.revisions if r.revision_number == revision_number), None)
    if match is None:
        raise RevisionNotFoundError(f"Revision {revision_number} not found")
    _apply_snapshot(doc, match.snapshot)
    _append_revision(doc, note=f"restore:{revision_number}")
    return save_document(doc)


def undo_document(document_id: str) -> DocumentRecord:
    doc = get_document(document_id)
    if doc is None:
        raise DocumentError("Document not found")
    if len(doc.revisions) < 2:
        raise DocumentError("Nothing to undo")
    target = doc.revisions[-2]
    return restore_revision(document_id, target.revision_number)


def diff_revisions(
    document_id: str,
    *,
    from_revision: int,
    to_revision: int,
) -> dict[str, Any]:
    doc = get_document(document_id)
    if doc is None:
        raise DocumentError("Document not found")

    def _snap(n: int) -> dict[str, Any]:
        if n == 0:
            # empty baseline
            return {}
        match = next((r for r in doc.revisions if r.revision_number == n), None)
        if match is None:
            raise RevisionNotFoundError(f"Revision {n} not found")
        return match.snapshot

    left = _snap(from_revision)
    right = _snap(to_revision)
    all_ids = sorted(set(left) | set(right))
    sections: dict[str, Any] = {}
    for sid in all_ids:
        l_content = (left.get(sid) or {}).get("content_json")
        r_content = (right.get(sid) or {}).get("content_json")
        changed = json.dumps(l_content, sort_keys=True) != json.dumps(r_content, sort_keys=True)
        sections[sid] = {
            "changed": changed,
            "before": l_content,
            "after": r_content,
            "before_locked": (left.get(sid) or {}).get("is_locked"),
            "after_locked": (right.get(sid) or {}).get("is_locked"),
        }
    return {
        "document_id": document_id,
        "from_revision": from_revision,
        "to_revision": to_revision,
        "sections": sections,
    }

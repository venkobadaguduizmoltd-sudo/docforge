"""Phase 2 document APIs: edit, regen, suggest, lock, versions, diff."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.documents.service import (
    DocumentError,
    RevisionNotFoundError,
    SectionLockedError,
    accept_suggestion,
    create_document_from_job_result,
    diff_revisions,
    edit_section,
    lock_section,
    regenerate_all_unlocked,
    regenerate_section,
    reject_suggestion,
    restore_revision,
    suggest_section,
    undo_document,
    unlock_section,
)
from app.documents.store import DocumentRecord, get_document, list_documents
from app.generation.schema import ContentOnlyViolation
from app.pipeline.job_store import get_job
from app.rbac.deps import get_current_user
from app.schemas.documents import (
    DiffOut,
    DocumentOut,
    RegenAllRequest,
    RevisionDetailOut,
    RevisionOut,
    SectionEditRequest,
    SectionOut,
    SectionRegenRequest,
    SuggestRequest,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def _section_out(sec) -> SectionOut:
    citations = sec.citations or sec.content_json.get("citations") or []
    return SectionOut(
        section_id=sec.section_id,
        content_json=sec.content_json,
        is_locked=sec.is_locked,
        citations=citations,
        pending_suggestion=sec.pending_suggestion,
        updated_at=sec.updated_at,
    )


def _doc_out(doc: DocumentRecord) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        title=doc.title,
        status=doc.status,
        source_job_id=doc.source_job_id,
        template_slug=doc.template_slug,
        template_sha256=doc.template_sha256,
        pinned_commit_sha=doc.pinned_commit_sha,
        sections=[_section_out(s) for s in doc.sections.values()],
        current_revision=doc.current_revision_number(),
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SectionLockedError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, RevisionNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ContentOnlyViolation):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, DocumentError):
        detail = str(exc)
        code = 404 if "not found" in detail.lower() else 400
        return HTTPException(status_code=code, detail=detail)
    return HTTPException(status_code=500, detail=str(exc))


@router.get("", response_model=list[DocumentOut])
def list_docs(_user=Depends(get_current_user)) -> list[DocumentOut]:
    return [_doc_out(d) for d in list_documents()]


@router.post("/from-job/{job_id}", response_model=DocumentOut)
def materialize_from_job(job_id: str, _user=Depends(get_current_user)) -> DocumentOut:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed" or not job.result:
        raise HTTPException(status_code=400, detail="Job is not completed")
    # Idempotent: return existing if already materialized
    for existing in list_documents():
        if existing.source_job_id == job_id:
            return _doc_out(existing)
    try:
        doc = create_document_from_job_result(job.result, job_id=job_id)
    except (DocumentError, ContentOnlyViolation) as exc:
        raise _http_error(exc) from exc
    return _doc_out(doc)


@router.get("/{document_id}", response_model=DocumentOut)
def get_doc(document_id: str, _user=Depends(get_current_user)) -> DocumentOut:
    doc = get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_out(doc)


@router.put("/{document_id}/sections/{section_id}", response_model=DocumentOut)
def put_section(
    document_id: str,
    section_id: str,
    body: SectionEditRequest,
    _user=Depends(get_current_user),
) -> DocumentOut:
    try:
        doc = edit_section(document_id, section_id, body.content)
    except (DocumentError, ContentOnlyViolation) as exc:
        raise _http_error(exc) from exc
    return _doc_out(doc)


@router.post("/{document_id}/sections/{section_id}/regenerate", response_model=DocumentOut)
async def post_regen_section(
    document_id: str,
    section_id: str,
    body: SectionRegenRequest | None = None,
    _user=Depends(get_current_user),
) -> DocumentOut:
    prompt = body.prompt if body else None
    try:
        doc = await regenerate_section(document_id, section_id, prompt=prompt)
    except (DocumentError, ContentOnlyViolation) as exc:
        raise _http_error(exc) from exc
    return _doc_out(doc)


@router.post("/{document_id}/regenerate", response_model=DocumentOut)
async def post_regen_all(
    document_id: str,
    body: RegenAllRequest | None = None,
    _user=Depends(get_current_user),
) -> DocumentOut:
    prompt = body.prompt if body else None
    try:
        doc = await regenerate_all_unlocked(document_id, prompt=prompt)
    except (DocumentError, ContentOnlyViolation) as exc:
        raise _http_error(exc) from exc
    return _doc_out(doc)


@router.post("/{document_id}/sections/{section_id}/suggest", response_model=DocumentOut)
async def post_suggest(
    document_id: str,
    section_id: str,
    body: SuggestRequest | None = None,
    _user=Depends(get_current_user),
) -> DocumentOut:
    prompt = body.prompt if body else None
    try:
        doc = await suggest_section(document_id, section_id, prompt=prompt)
    except (DocumentError, ContentOnlyViolation) as exc:
        raise _http_error(exc) from exc
    return _doc_out(doc)


@router.post(
    "/{document_id}/sections/{section_id}/suggestions/accept",
    response_model=DocumentOut,
)
def post_accept(document_id: str, section_id: str, _user=Depends(get_current_user)) -> DocumentOut:
    try:
        doc = accept_suggestion(document_id, section_id)
    except (DocumentError, ContentOnlyViolation) as exc:
        raise _http_error(exc) from exc
    return _doc_out(doc)


@router.post(
    "/{document_id}/sections/{section_id}/suggestions/reject",
    response_model=DocumentOut,
)
def post_reject(document_id: str, section_id: str, _user=Depends(get_current_user)) -> DocumentOut:
    try:
        doc = reject_suggestion(document_id, section_id)
    except DocumentError as exc:
        raise _http_error(exc) from exc
    return _doc_out(doc)


@router.post("/{document_id}/sections/{section_id}/lock", response_model=DocumentOut)
def post_lock(document_id: str, section_id: str, _user=Depends(get_current_user)) -> DocumentOut:
    try:
        doc = lock_section(document_id, section_id)
    except DocumentError as exc:
        raise _http_error(exc) from exc
    return _doc_out(doc)


@router.post("/{document_id}/sections/{section_id}/unlock", response_model=DocumentOut)
def post_unlock(document_id: str, section_id: str, _user=Depends(get_current_user)) -> DocumentOut:
    try:
        doc = unlock_section(document_id, section_id)
    except DocumentError as exc:
        raise _http_error(exc) from exc
    return _doc_out(doc)


@router.get("/{document_id}/versions", response_model=list[RevisionOut])
def list_versions(document_id: str, _user=Depends(get_current_user)) -> list[RevisionOut]:
    doc = get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return [
        RevisionOut(revision_number=r.revision_number, note=r.note, created_at=r.created_at)
        for r in doc.revisions
    ]


@router.get("/{document_id}/versions/{revision_number}", response_model=RevisionDetailOut)
def get_version(
    document_id: str, revision_number: int, _user=Depends(get_current_user)
) -> RevisionDetailOut:
    doc = get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    match = next((r for r in doc.revisions if r.revision_number == revision_number), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Revision not found")
    return RevisionDetailOut(
        revision_number=match.revision_number,
        note=match.note,
        created_at=match.created_at,
        snapshot=match.snapshot,
    )


@router.get("/{document_id}/diff", response_model=DiffOut)
def get_diff(
    document_id: str,
    from_revision: int = Query(..., alias="from"),
    to_revision: int = Query(..., alias="to"),
    _user=Depends(get_current_user),
) -> DiffOut:
    try:
        data = diff_revisions(document_id, from_revision=from_revision, to_revision=to_revision)
    except (DocumentError, RevisionNotFoundError) as exc:
        raise _http_error(exc) from exc
    return DiffOut(**data)


@router.post("/{document_id}/versions/{revision_number}/restore", response_model=DocumentOut)
def post_restore(
    document_id: str, revision_number: int, _user=Depends(get_current_user)
) -> DocumentOut:
    try:
        doc = restore_revision(document_id, revision_number)
    except (DocumentError, RevisionNotFoundError) as exc:
        raise _http_error(exc) from exc
    return _doc_out(doc)


@router.post("/{document_id}/undo", response_model=DocumentOut)
def post_undo(document_id: str, _user=Depends(get_current_user)) -> DocumentOut:
    try:
        doc = undo_document(document_id)
    except DocumentError as exc:
        raise _http_error(exc) from exc
    return _doc_out(doc)

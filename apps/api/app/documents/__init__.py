"""Phase 2 document corrections, versions, and section operations."""

from app.documents.store import (
    DocumentRecord,
    RevisionRecord,
    SectionRecord,
    clear_documents,
    get_document,
    list_documents,
    save_document,
)
from app.documents.service import (
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

__all__ = [
    "DocumentRecord",
    "RevisionRecord",
    "SectionRecord",
    "accept_suggestion",
    "clear_documents",
    "create_document_from_job_result",
    "diff_revisions",
    "edit_section",
    "get_document",
    "list_documents",
    "lock_section",
    "regenerate_all_unlocked",
    "regenerate_section",
    "reject_suggestion",
    "restore_revision",
    "save_document",
    "suggest_section",
    "undo_document",
    "unlock_section",
]

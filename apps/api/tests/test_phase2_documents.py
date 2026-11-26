"""Phase 2: section regen/edit/suggest/lock/versions — section-only + immutability."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

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
from app.documents.store import clear_documents, get_document
from app.generation.schema import ContentOnlyViolation, validate_section_content
from app.pipeline.generate import run_generate_document
from app.pipeline.progress import clear_local_progress
from app.services.templates import compute_spec_sha256, load_builtin_template


@pytest.fixture(autouse=True)
def _clean() -> None:
    clear_local_progress()
    clear_documents()
    yield
    clear_local_progress()
    clear_documents()


@pytest.fixture
async def generated_doc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    from app.core.config import get_settings

    get_settings.cache_clear()
    result = await run_generate_document(
        "phase2-job",
        {
            "provider": "fixture",
            "full_name": "docforge/sample",
            "ref": "main",
            "template_slug": "tech-overview",
            "output_dir": str(tmp_path / "out"),
            "cleanup": False,
        },
    )
    doc = create_document_from_job_result(result, job_id="phase2-job")
    return doc, result


def _canonical(content: dict) -> bytes:
    return json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")


@pytest.mark.asyncio
async def test_section_regen_only_changes_target(generated_doc) -> None:
    doc, _ = generated_doc
    before = {sid: _canonical(sec.content_json) for sid, sec in doc.sections.items()}
    seal = doc.template_sha256

    updated = await regenerate_section(
        doc.id,
        "overview",
        prompt="Emphasize security scanning and redaction.",
    )
    assert updated.sections["overview"].content_json["summary"] != json.loads(
        before["overview"].decode()
    )["summary"]
    for sid, blob in before.items():
        if sid == "overview":
            continue
        assert _canonical(updated.sections[sid].content_json) == blob

    # Template immutability still holds
    loaded = load_builtin_template("tech-overview")
    assert compute_spec_sha256(loaded["spec"]) == seal == loaded["sha256"]


@pytest.mark.asyncio
async def test_manual_edit_and_content_only(generated_doc) -> None:
    doc, _ = generated_doc
    before_arch = _canonical(doc.sections["architecture"].content_json)
    edited = edit_section(
        doc.id,
        "overview",
        {
            "summary": "Manually edited overview summary.",
            "bullets": ["Edited bullet"],
            "code_refs": [],
            "notes": "human",
            "citations": [{"file": "src/app.py", "line": 1, "commit_sha": doc.pinned_commit_sha}],
        },
    )
    assert edited.sections["overview"].content_json["summary"].startswith("Manually")
    assert _canonical(edited.sections["architecture"].content_json) == before_arch
    cites = edited.sections["overview"].citations
    assert cites and cites[0]["file"] == "src/app.py"

    with pytest.raises(ContentOnlyViolation):
        edit_section(
            doc.id,
            "overview",
            {"summary": "x", "template": {"hack": True}},
        )


@pytest.mark.asyncio
async def test_suggestion_accept_reject(generated_doc) -> None:
    doc, _ = generated_doc
    original = copy.deepcopy(doc.sections["key_modules"].content_json)
    suggested = await suggest_section(doc.id, "key_modules", prompt="Make bullets sharper.")
    pending = suggested.sections["key_modules"].pending_suggestion
    assert pending is not None
    assert pending["proposed"]["summary"] != original["summary"] or pending["proposed"] != original
    # Content unchanged until accept
    assert suggested.sections["key_modules"].content_json == original

    rejected = reject_suggestion(doc.id, "key_modules")
    assert rejected.sections["key_modules"].pending_suggestion is None
    assert rejected.sections["key_modules"].content_json == original

    await suggest_section(doc.id, "key_modules")
    before_others = {
        sid: _canonical(sec.content_json)
        for sid, sec in get_document(doc.id).sections.items()
        if sid != "key_modules"
    }
    accepted = accept_suggestion(doc.id, "key_modules")
    assert accepted.sections["key_modules"].pending_suggestion is None
    assert accepted.sections["key_modules"].content_json != original
    for sid, blob in before_others.items():
        assert _canonical(accepted.sections[sid].content_json) == blob


@pytest.mark.asyncio
async def test_locks_skip_regenerate_all(generated_doc) -> None:
    doc, _ = generated_doc
    lock_section(doc.id, "architecture")
    before = {sid: _canonical(sec.content_json) for sid, sec in get_document(doc.id).sections.items()}

    updated = await regenerate_all_unlocked(
        doc.id, prompt="Refresh unlocked sections with more detail."
    )
    assert _canonical(updated.sections["architecture"].content_json) == before["architecture"]
    # At least one unlocked section should differ when follow-up is applied
    changed = [
        sid
        for sid in ("overview", "key_modules")
        if _canonical(updated.sections[sid].content_json) != before[sid]
    ]
    assert changed, "expected unlocked sections to regenerate"

    unlock_section(doc.id, "architecture")
    assert get_document(doc.id).sections["architecture"].is_locked is False


@pytest.mark.asyncio
async def test_versions_diff_undo_restore(generated_doc) -> None:
    doc, _ = generated_doc
    assert doc.current_revision_number() == 1
    edit_section(
        doc.id,
        "overview",
        {"summary": "Version two summary.", "bullets": ["v2"], "code_refs": []},
    )
    doc = get_document(doc.id)
    assert doc.current_revision_number() == 2
    v1_summary = doc.revisions[0].snapshot["overview"]["content_json"]["summary"]

    edit_section(
        doc.id,
        "overview",
        {"summary": "Version three summary.", "bullets": ["v3"], "code_refs": []},
    )
    diff = diff_revisions(doc.id, from_revision=1, to_revision=3)
    assert diff["sections"]["overview"]["changed"] is True
    assert diff["sections"]["architecture"]["changed"] is False

    undone = undo_document(doc.id)
    # undo restores revision 2 content then appends a new revision
    assert undone.sections["overview"].content_json["summary"] == "Version two summary."

    restored = restore_revision(doc.id, 1)
    assert restored.sections["overview"].content_json["summary"] == v1_summary


@pytest.mark.asyncio
async def test_citations_surfaced_on_materialize(generated_doc) -> None:
    doc, result = generated_doc
    assert doc.pinned_commit_sha == result["commit_sha"]
    for section in doc.sections.values():
        assert isinstance(section.citations, list)
        # Fixture analysis has symbols/files → citations attached
        assert section.citations, f"expected citations on {section.section_id}"
        cite = section.citations[0]
        assert cite.get("file")
        assert cite.get("commit_sha") == doc.pinned_commit_sha
        # Also present inside content_json for API/UI
        assert section.content_json.get("citations")


def test_validate_section_accepts_citations() -> None:
    content = validate_section_content(
        "overview",
        {
            "summary": "With cite",
            "citations": [{"file": "a.py", "line": 10, "commit_sha": "abc"}],
        },
    )
    assert content.citations[0].file == "a.py"

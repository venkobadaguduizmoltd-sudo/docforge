"""End-to-end generation path: fixture repo → content → HTML/DOCX/PDF."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.generation.llm import MockLLMClient
from app.generation.schema import ContentOnlyViolation, validate_document_content, validate_section_content
from app.pipeline.generate import run_generate_document
from app.pipeline.progress import clear_local_progress
from app.services.templates import compute_spec_sha256, load_builtin_template


@pytest.fixture(autouse=True)
def _clean_progress() -> None:
    clear_local_progress()
    yield
    clear_local_progress()


@pytest.mark.asyncio
async def test_generate_document_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    from app.core.config import get_settings

    get_settings.cache_clear()

    job_id = "test-job-1"
    result = await run_generate_document(
        job_id,
        {
            "provider": "fixture",
            "full_name": "docforge/sample",
            "ref": "main",
            "template_slug": "tech-overview",
            "output_dir": str(tmp_path / "out"),
            "cleanup": False,
        },
    )
    assert result["commit_sha"]
    assert set(result["content"]) == {"overview", "architecture", "key_modules"}
    artifacts = result["artifacts"]
    assert Path(artifacts["html"]).exists()
    assert Path(artifacts["docx"]).exists()
    assert Path(artifacts["pdf"]).exists()
    html = Path(artifacts["html"]).read_text(encoding="utf-8")
    assert "Technical Overview" in html or "Overview" in html
    assert "Auto-generated" in html or "overview" in html.lower()


def test_section_content_only_rule() -> None:
    ok = validate_section_content(
        "overview",
        {"summary": "Hello", "bullets": ["a"], "code_refs": []},
    )
    assert ok.summary == "Hello"
    with pytest.raises(ContentOnlyViolation):
        validate_section_content("overview", {"summary": "x", "template": {"hack": True}})
    with pytest.raises(ContentOnlyViolation):
        validate_document_content(
            {"overview": {"summary": "x"}, "extra": {"summary": "y"}},
            {"overview", "architecture"},
        )


def test_template_immutability_checksum_seal() -> None:
    loaded = load_builtin_template("tech-overview")
    assert loaded["immutable"] is True
    assert loaded["sha256"] == compute_spec_sha256(loaded["spec"])
    mutated = dict(loaded["spec"])
    mutated["name"] = "Mutated"
    assert compute_spec_sha256(mutated) != loaded["sha256"]


@pytest.mark.asyncio
async def test_mock_llm_returns_valid_section() -> None:
    client = MockLLMClient()
    data = await client.complete_json(system="sys", user="section_id='architecture' please")
    content = validate_section_content("architecture", data)
    assert content.summary


def test_render_refuses_checksum_mismatch(tmp_path: Path) -> None:
    from app.generation.schema import SectionContent
    from app.rendering.html import render_html

    loaded = load_builtin_template("tech-overview")
    content = {
        sid: SectionContent(summary=f"Body for {sid}", bullets=[])
        for sid in ("overview", "architecture", "key_modules")
    }
    with pytest.raises(ValueError, match="checksum"):
        render_html(
            template_spec=loaded["spec"],
            content=content,
            theme_dir=loaded["theme_dir"],
            expected_sha256="0" * 64,
        )

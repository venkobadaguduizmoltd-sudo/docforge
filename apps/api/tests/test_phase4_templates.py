"""Phase 4 — template studio schema, lifecycle, checksum, DOCX import."""

from __future__ import annotations

from io import BytesIO

import pytest
from docx import Document

from app.services.templates import compute_spec_sha256, load_builtin_template
from app.template_studio.docx_import import draft_spec_from_docx
from app.template_studio.prompt import draft_spec_from_prompt
from app.template_studio.schema import TemplateSpecValidationError, validate_template_spec
from app.template_studio.store import (
    clone_template,
    create_template,
    deprecate_template,
    mark_test_run,
    publish_template,
    replace_draft_spec,
    reset_store,
)
from app.template_studio.yaml_codec import spec_from_yaml, spec_to_yaml


@pytest.fixture(autouse=True)
def _clean_store() -> None:
    reset_store()
    yield
    reset_store()


def test_builtin_five_plus_tech_overview_sealed() -> None:
    slugs = [
        "tech-overview",
        "software-design-document",
        "api-reference",
        "readme-developer-guide",
        "onboarding-guide",
        "runbook-operations",
    ]
    for slug in slugs:
        loaded = load_builtin_template(slug)
        assert loaded["immutable"] is True
        assert compute_spec_sha256(loaded["spec"]) == loaded["sha256"]
        validate_template_spec(loaded["spec"])


def test_schema_rejects_bad_section_id() -> None:
    with pytest.raises(TemplateSpecValidationError):
        validate_template_spec(
            {
                "id": "x",
                "name": "X",
                "slug": "x",
                "sections": [{"id": "Bad-Id", "title": "Nope"}],
            }
        )


def test_prompt_draft_validates() -> None:
    spec = draft_spec_from_prompt("Create an API reference with authentication and endpoints")
    assert "api" in {s["id"] for s in spec["sections"]} or any(
        "api" in t for t in spec.get("tags", [])
    )
    validate_template_spec(spec)


def test_yaml_round_trip() -> None:
    spec = draft_spec_from_prompt("Onboarding guide for new hires")
    text = spec_to_yaml(spec)
    again = spec_from_yaml(text)
    assert again["slug"] == spec["slug"]
    assert compute_spec_sha256(again) == compute_spec_sha256(spec)


def test_docx_import_headings() -> None:
    doc = Document()
    doc.add_heading("Ops Runbook", level=1)
    doc.add_heading("Deploy", level=2)
    doc.add_heading("Rollback", level=2)
    buf = BytesIO()
    doc.save(buf)
    spec = draft_spec_from_docx(buf.getvalue())
    ids = [s["id"] for s in spec["sections"]]
    assert len(ids) == 3
    assert len(ids) == len(set(ids))


def test_lifecycle_draft_publish_deprecate_and_immutability() -> None:
    record = create_template(name="Lifecycle Demo", tags=["test"])
    assert record.status == "draft"
    current = record.current_version()
    assert current is not None
    assert current.is_immutable is False

    replace_draft_spec(
        record.id,
        {
            **current.spec_json,
            "sections": [
                {
                    "id": "overview",
                    "title": "Overview",
                    "description": "d",
                    "instructions": "i",
                },
                {
                    "id": "details",
                    "title": "Details",
                    "description": "d",
                    "instructions": "i",
                },
            ],
        },
    )

    with pytest.raises(PermissionError, match="test run"):
        publish_template(record.id)

    mark_test_run(record.id, ok=True, job_id="job-1")
    published = publish_template(record.id)
    assert published.status == "published"
    assert published.current_version().is_immutable is True
    seal = published.current_version().sha256

    with pytest.raises(PermissionError, match="immutable"):
        replace_draft_spec(record.id, published.current_version().spec_json)

    assert published.current_version().sha256 == seal

    cloned = clone_template(record.id, new_name="Lifecycle Demo Copy")
    assert cloned.status == "draft"
    assert cloned.slug != published.slug

    deprecated = deprecate_template(published.id)
    assert deprecated.status == "deprecated"

"""DOCX renderer from the same content+template merge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.generation.schema import SectionContent
from app.services.templates import compute_spec_sha256


def render_docx(
    *,
    template_spec: dict[str, Any],
    content: dict[str, SectionContent],
    output_path: Path,
    expected_sha256: str | None = None,
) -> Path:
    if expected_sha256:
        actual = compute_spec_sha256(template_spec)
        if actual != expected_sha256:
            raise ValueError("Template checksum mismatch — refusing to render")

    document = Document()
    title = document.add_heading(template_spec.get("name", "Document"), level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    for section in template_spec.get("sections", []):
        sid = section["id"]
        body = content[sid]
        document.add_heading(body.title or section.get("title") or sid, level=1)
        document.add_paragraph(body.summary)
        for bullet in body.bullets:
            document.add_paragraph(bullet, style="List Bullet")
        if body.code_refs:
            document.add_paragraph("Code references:")
            for ref in body.code_refs:
                document.add_paragraph(ref, style="List Number")
        if body.notes:
            document.add_paragraph(body.notes)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
    return output_path

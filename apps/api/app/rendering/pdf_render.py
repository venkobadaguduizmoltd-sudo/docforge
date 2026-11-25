"""PDF renderer via ReportLab from the same content+template merge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from app.generation.schema import SectionContent
from app.services.templates import compute_spec_sha256


def render_pdf(
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    story: list[Any] = []
    story.append(Paragraph(template_spec.get("name", "Document"), styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))

    for section in template_spec.get("sections", []):
        sid = section["id"]
        body = content[sid]
        heading = body.title or section.get("title") or sid
        story.append(Paragraph(heading, styles["Heading1"]))
        story.append(Paragraph(body.summary, styles["BodyText"]))
        if body.bullets:
            items = [ListItem(Paragraph(b, styles["BodyText"])) for b in body.bullets]
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=20))
        if body.code_refs:
            story.append(Paragraph("Code references:", styles["Heading3"]))
            for ref in body.code_refs:
                story.append(Paragraph(ref, styles["Code"]))
        if body.notes:
            story.append(Paragraph(body.notes, styles["Italic"]))
        story.append(Spacer(1, 0.15 * inch))

    doc.build(story)
    return output_path

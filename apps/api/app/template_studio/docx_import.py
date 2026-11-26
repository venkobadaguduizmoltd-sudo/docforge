"""Import a draft template structure from DOCX headings."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any

from docx import Document

from app.template_studio.schema import validate_template_spec
from app.template_studio.store import slugify


def _heading_level(style_name: str | None) -> int | None:
    if not style_name:
        return None
    match = re.match(r"Heading\s+(\d+)", style_name, flags=re.I)
    if not match:
        return None
    return int(match.group(1))


def _section_id(title: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", title.strip().lower()).strip("_")
    if not base or not base[0].isalpha():
        base = f"section_{base}" if base else "section"
    base = base[:64]
    candidate = base
    n = 2
    while candidate in used:
        candidate = f"{base}_{n}"[:64]
        n += 1
    used.add(candidate)
    return candidate


def draft_spec_from_docx(
    data: bytes,
    *,
    name: str | None = None,
    max_level: int = 2,
) -> dict[str, Any]:
    """Walk DOCX paragraphs; Heading 1–N become sections (default H1–H2)."""
    document = Document(BytesIO(data))
    titles: list[str] = []
    for paragraph in document.paragraphs:
        level = _heading_level(paragraph.style.name if paragraph.style else None)
        if level is None or level > max_level:
            continue
        text = paragraph.text.strip()
        if text:
            titles.append(text)
    if not titles:
        raise ValueError("No headings found in DOCX (expected Heading 1–2)")

    used: set[str] = set()
    sections = [
        {
            "id": _section_id(title, used),
            "title": title,
            "description": f"Imported from DOCX heading: {title}",
            "instructions": f"Fill the '{title}' section from the repository.",
        }
        for title in titles
    ]
    resolved_name = name or titles[0]
    slug = slugify(resolved_name)
    spec: dict[str, Any] = {
        "id": f"studio.{slug}",
        "name": resolved_name,
        "slug": slug,
        "description": f"Imported from DOCX ({len(sections)} sections).",
        "tags": ["imported", "docx"],
        "theme": {
            "html": "theme/document.html.j2",
            "css": "theme/styles.css",
            "docx": "theme/docx-styles.json",
        },
        "sections": sections,
    }
    return validate_template_spec(spec)

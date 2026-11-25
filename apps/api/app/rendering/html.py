"""HTML preview renderer — merges section content into template theme."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.generation.schema import SectionContent
from app.services.templates import compute_spec_sha256


def render_html(
    *,
    template_spec: dict[str, Any],
    content: dict[str, SectionContent],
    theme_dir: Path,
    expected_sha256: str | None = None,
) -> str:
    if expected_sha256:
        actual = compute_spec_sha256(template_spec)
        if actual != expected_sha256:
            raise ValueError("Template checksum mismatch — refusing to render")

    env = Environment(
        loader=FileSystemLoader(str(theme_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("document.html.j2")
    sections_out = []
    for section in template_spec.get("sections", []):
        sid = section["id"]
        body = content[sid]
        sections_out.append(
            {
                "id": sid,
                "title": body.title or section.get("title") or sid,
                "summary": body.summary,
                "bullets": body.bullets,
                "code_refs": body.code_refs,
                "notes": body.notes,
            }
        )
    return template.render(
        doc_title=template_spec.get("name", "Document"),
        sections=sections_out,
        theme=template_spec.get("theme", {}),
    )

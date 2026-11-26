"""Prompt-to-template draft — heuristic + optional provider completion."""

from __future__ import annotations

import json
import re
from typing import Any

from app.template_studio.schema import validate_template_spec
from app.template_studio.store import slugify

_SECTION_BANK: list[tuple[str, str, str, list[str]]] = [
    ("overview", "Overview", "Purpose and scope.", ["overview", "summary", "about"]),
    ("goals", "Goals", "Product or doc goals.", ["goal", "objective"]),
    ("architecture", "Architecture", "System structure.", ["architect", "design", "component"]),
    ("api", "API Surface", "Endpoints and contracts.", ["api", "endpoint", "rest", "graphql"]),
    ("data_model", "Data Model", "Entities and storage.", ["data", "schema", "model", "database"]),
    ("security", "Security", "Authn/z and threats.", ["security", "auth", "threat"]),
    ("setup", "Setup", "Install and configure.", ["setup", "install", "getting started", "readme"]),
    ("development", "Development", "Local workflows.", ["develop", "contribute", "dev"]),
    ("onboarding", "Onboarding", "First-week checklist.", ["onboard", "new hire", "welcome"]),
    ("runbook", "Runbook", "Operate and recover.", ["runbook", "ops", "incident", "operations"]),
    ("monitoring", "Monitoring", "Signals and alerts.", ["monitor", "alert", "slo", "observ"]),
    ("faq", "FAQ", "Common questions.", ["faq", "question"]),
]


def _pick_sections(description: str, *, max_sections: int = 6) -> list[dict[str, Any]]:
    text = description.lower()
    picked: list[dict[str, Any]] = []
    for sid, title, desc, keywords in _SECTION_BANK:
        if any(k in text for k in keywords):
            picked.append(
                {
                    "id": sid,
                    "title": title,
                    "description": desc,
                    "instructions": f"Write the {title} section based on the repository. {desc}",
                }
            )
    if not picked:
        picked = [
            {
                "id": "overview",
                "title": "Overview",
                "description": "High-level summary.",
                "instructions": "Summarize the repository purpose and audience.",
            },
            {
                "id": "details",
                "title": "Details",
                "description": "Core details for this document type.",
                "instructions": description.strip() or "Expand on the main topics.",
            },
        ]
    # Always lead with overview if missing
    if picked[0]["id"] != "overview" and any(s["id"] == "overview" for s in picked):
        overview = next(s for s in picked if s["id"] == "overview")
        picked = [overview] + [s for s in picked if s["id"] != "overview"]
    return picked[:max_sections]


def draft_spec_from_prompt(description: str, *, name: str | None = None) -> dict[str, Any]:
    """Deterministic structure draft from a natural-language description."""
    desc = description.strip()
    if not desc:
        raise ValueError("description is required")
    title = name or _guess_name(desc)
    slug = slugify(title)
    sections = _pick_sections(desc)
    tags = _guess_tags(desc)
    spec: dict[str, Any] = {
        "id": f"studio.{slug}",
        "name": title,
        "slug": slug,
        "description": desc[:500],
        "tags": tags,
        "theme": {
            "html": "theme/document.html.j2",
            "css": "theme/styles.css",
            "docx": "theme/docx-styles.json",
        },
        "sections": sections,
    }
    return validate_template_spec(spec)


def _guess_name(description: str) -> str:
    first = description.strip().split("\n", 1)[0].strip()
    first = re.sub(r"^(create|build|make|design)\s+(a|an|the)\s+", "", first, flags=re.I)
    if len(first) > 60:
        first = first[:57] + "…"
    return first.title() if first else "Draft Template"


def _guess_tags(description: str) -> list[str]:
    text = description.lower()
    tags = ["studio"]
    mapping = {
        "api": "api",
        "readme": "readme",
        "onboard": "onboarding",
        "runbook": "operations",
        "design": "design",
        "ops": "operations",
        "security": "security",
    }
    for needle, tag in mapping.items():
        if needle in text and tag not in tags:
            tags.append(tag)
    return tags


async def draft_spec_with_provider(description: str, provider: Any | None) -> dict[str, Any]:
    """
    Prefer provider JSON completion when available; fall back to heuristic.

    Provider must expose `async complete(prompt: str) -> Any` with text/json content.
    """
    if provider is None:
        return draft_spec_from_prompt(description)
    prompt = (
        "Return ONLY JSON for a DocForge template structure with keys "
        "id,name,slug,description,tags,theme,sections. "
        "Each section needs id,title,description,instructions. "
        f"Description:\n{description}"
    )
    try:
        result = await provider.complete(prompt)
        raw = getattr(result, "text", None) or getattr(result, "content", None) or result
        if isinstance(raw, dict):
            data = raw
        else:
            text = str(raw)
            start = text.find("{")
            end = text.rfind("}")
            data = json.loads(text[start : end + 1])
        if "theme" not in data:
            data["theme"] = {
                "html": "theme/document.html.j2",
                "css": "theme/styles.css",
                "docx": "theme/docx-styles.json",
            }
        if "slug" not in data:
            data["slug"] = slugify(str(data.get("name") or "draft"))
        if "id" not in data:
            data["id"] = f"studio.{data['slug']}"
        return validate_template_spec(data)
    except Exception:
        return draft_spec_from_prompt(description)

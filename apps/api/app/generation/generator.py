"""Generate schema-validated section content from repository analysis."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.analysis.analyzer import AnalysisResult
from app.generation.llm import LLMClient, get_llm_client
from app.generation.schema import ContentOnlyViolation, SectionContent, validate_section_content
from app.security.prompt_wrap import SYSTEM_GUARD, build_section_prompt

ProgressCb = Callable[[str, dict[str, Any]], Awaitable[None]]


SCHEMA_HINT = (
    '{"title": string|null, "summary": string, "bullets": string[], '
    '"code_refs": string[], "notes": string|null, '
    '"citations": [{"file": string, "line": number|null, "end_line": number|null, '
    '"commit_sha": string|null, "symbol": string|null}]}'
)


async def generate_section_content(
    *,
    section_id: str,
    section_title: str,
    analysis: AnalysisResult,
    llm: LLMClient | None = None,
    follow_up_prompt: str | None = None,
) -> SectionContent:
    client = llm or get_llm_client()
    prompt = build_section_prompt(
        section_id=section_id,
        section_title=section_title,
        schema_hint=SCHEMA_HINT,
        repo_blob=analysis.prompt_blob(),
        follow_up_prompt=follow_up_prompt,
    )
    raw = await client.complete_json(system=SYSTEM_GUARD, user=prompt)
    return validate_section_content(section_id, raw)


async def generate_document_content(
    *,
    sections: list[dict[str, Any]],
    analysis: AnalysisResult,
    llm: LLMClient | None = None,
    on_progress: ProgressCb | None = None,
) -> dict[str, SectionContent]:
    """sections: list of template section dicts with id/title."""
    client = llm or get_llm_client()
    allowed = {str(s["id"]) for s in sections}
    results: dict[str, SectionContent] = {}
    for index, section in enumerate(sections, start=1):
        section_id = str(section["id"])
        title = str(section.get("title") or section_id)
        if on_progress:
            await on_progress(
                "generating_section",
                {"section_id": section_id, "index": index, "total": len(sections)},
            )
        content = await generate_section_content(
            section_id=section_id,
            section_title=title,
            analysis=analysis,
            llm=client,
        )
        results[section_id] = content
    # Enforce content-only / exact section set
    if set(results) != allowed:
        raise ContentOnlyViolation("Generated sections do not match template section ids")
    return results

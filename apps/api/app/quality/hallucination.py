"""Validate generated content against analysis — no invented paths/symbols/endpoints."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.analysis.analyzer import AnalysisResult
from app.generation.schema import SectionContent

_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_])((?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]+)(?![A-Za-z0-9_])"
)
_ENDPOINT_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/\S+)")


@dataclass
class HallucinationIssue:
    kind: str
    value: str
    section_id: str
    detail: str


@dataclass
class HallucinationReport:
    ok: bool
    issues: list[HallucinationIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": [
                {"kind": i.kind, "value": i.value, "section_id": i.section_id, "detail": i.detail}
                for i in self.issues
            ],
        }


def _indexes(analysis: AnalysisResult) -> tuple[set[str], set[str], set[tuple[str, str]]]:
    files = set(analysis.files)
    symbols = {s.name for s in analysis.symbols}
    endpoints: set[tuple[str, str]] = set()
    openapi = (analysis.extractors or {}).get("openapi") or {}
    for item in openapi.get("endpoints") or []:
        endpoints.add((str(item.get("method", "")).upper(), str(item.get("path", ""))))
    return files, symbols, endpoints


def validate_section_against_analysis(
    section_id: str,
    content: SectionContent,
    analysis: AnalysisResult,
) -> list[HallucinationIssue]:
    files, symbols, endpoints = _indexes(analysis)
    issues: list[HallucinationIssue] = []

    # Explicit citations / code_refs
    for ref in content.code_refs:
        path = ref.split(":", 1)[0].strip()
        if path and path not in files and not any(f.endswith("/" + path) or f == path for f in files):
            issues.append(
                HallucinationIssue(
                    kind="path",
                    value=path,
                    section_id=section_id,
                    detail="code_refs path not present in repository analysis",
                )
            )
    for cite in content.citations:
        if cite.file and cite.file not in files:
            issues.append(
                HallucinationIssue(
                    kind="path",
                    value=cite.file,
                    section_id=section_id,
                    detail="citation.file not present in repository analysis",
                )
            )
        if cite.symbol and cite.symbol not in symbols:
            issues.append(
                HallucinationIssue(
                    kind="symbol",
                    value=cite.symbol,
                    section_id=section_id,
                    detail="citation.symbol not present in repository analysis",
                )
            )

    blob = " ".join(
        [
            content.summary or "",
            " ".join(content.bullets or []),
            content.notes or "",
            " ".join(content.code_refs or []),
        ]
    )
    for match in _PATH_RE.finditer(blob):
        path = match.group(1)
        if path.startswith("http"):
            continue
        if path not in files and not any(f.endswith(path) for f in files):
            issues.append(
                HallucinationIssue(
                    kind="path",
                    value=path,
                    section_id=section_id,
                    detail="path-like token in prose not found in analysis files",
                )
            )
    for match in _ENDPOINT_RE.finditer(blob):
        method, path = match.group(1).upper(), match.group(2).rstrip(".,);]")
        if endpoints and (method, path) not in endpoints:
            issues.append(
                HallucinationIssue(
                    kind="endpoint",
                    value=f"{method} {path}",
                    section_id=section_id,
                    detail="HTTP endpoint not present in extracted OpenAPI",
                )
            )
    return issues


def validate_document_against_analysis(
    content_by_section: dict[str, SectionContent],
    analysis: AnalysisResult,
) -> HallucinationReport:
    issues: list[HallucinationIssue] = []
    for section_id, content in content_by_section.items():
        issues.extend(validate_section_against_analysis(section_id, content, analysis))
    return HallucinationReport(ok=len(issues) == 0, issues=issues)

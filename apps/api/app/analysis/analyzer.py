"""Repository analyzer: file tree, languages, symbols, extractors, summaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.analysis.extractors import run_extractors
from app.analysis.languages import detect_language, summarize_languages
from app.analysis.summarize import hierarchical_summaries
from app.analysis.symbols import Symbol, extract_symbols
from app.security.docignore import is_ignored, load_docignore
from app.security.prompt_wrap import neutralize_injection_phrases
from app.security.secrets import redact_text

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
}

MAX_FILE_BYTES = 200_000
MAX_FILES = 400


@dataclass
class AnalysisResult:
    root: str
    files: list[str]
    tree: list[str]
    languages: dict[str, int]
    symbols: list[Symbol] = field(default_factory=list)
    redacted_excerpts: dict[str, str] = field(default_factory=dict)
    secret_findings_count: int = 0
    ignored_files: list[str] = field(default_factory=list)
    extractors: dict[str, Any] = field(default_factory=dict)
    summaries: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["symbols"] = [asdict(s) for s in self.symbols]
        return data

    def prompt_blob(self, *, max_chars: int = 24_000) -> str:
        parts = [
            f"Files ({len(self.files)}):",
            "\n".join(self.tree[:200]),
            "",
            f"Languages: {self.languages}",
            "",
            "Symbols:",
        ]
        for sym in self.symbols[:80]:
            parts.append(f"- {sym.kind} {sym.name} @ {sym.path}:{sym.line}")
        if self.extractors:
            openapi = self.extractors.get("openapi") or {}
            endpoints = openapi.get("endpoints") or []
            if endpoints:
                parts.append("")
                parts.append("OpenAPI endpoints:")
                for ep in endpoints[:40]:
                    parts.append(f"- {ep.get('method')} {ep.get('path')}")
            deps = (self.extractors.get("dependencies") or {}).get("packages") or []
            if deps:
                parts.append("")
                parts.append("Dependencies:")
                for pkg in deps[:40]:
                    parts.append(f"- {pkg.get('ecosystem')}:{pkg.get('name')}")
            env_keys = (self.extractors.get("env_keys") or {}).get("keys") or []
            if env_keys:
                parts.append("")
                parts.append("Env keys (names only): " + ", ".join(env_keys[:40]))
        if self.summaries.get("repo"):
            parts.append("")
            parts.append("Repo summary:")
            parts.append(str(self.summaries["repo"].get("summary") or ""))
        parts.append("")
        parts.append("File excerpts (redacted):")
        used = 0
        for path, excerpt in list(self.redacted_excerpts.items())[:40]:
            chunk = f"\n--- {path} ---\n{excerpt}\n"
            if used + len(chunk) > max_chars:
                break
            parts.append(chunk)
            used += len(chunk)
        return "\n".join(parts)


def _iter_files(root: Path, patterns: list[str]) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    ignored: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        if is_ignored(rel, patterns):
            ignored.append(rel)
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        files.append(path)
        if len(files) >= MAX_FILES:
            break
    return files, ignored


def build_tree_lines(root: Path, files: list[Path]) -> list[str]:
    lines: list[str] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        lines.append(rel)
    return lines


def analyze_repository(root: Path) -> AnalysisResult:
    root = root.resolve()
    patterns = load_docignore(root)
    files, ignored = _iter_files(root, patterns)
    rels = [p.relative_to(root).as_posix() for p in files]
    languages = summarize_languages(rels)
    symbols: list[Symbol] = []
    excerpts: dict[str, str] = {}
    secret_count = 0

    for path, rel in zip(files, rels, strict=True):
        lang = detect_language(rel)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        redacted, findings = redact_text(text, path=rel)
        redacted = neutralize_injection_phrases(redacted)
        secret_count += len(findings)
        symbols.extend(extract_symbols(rel, redacted, lang))
        if lang in {"Python", "JavaScript", "TypeScript", "Markdown", "Go", "Rust"} or rel.endswith(
            ("README.md", "pyproject.toml", "package.json", "openapi.json", "openapi.yaml")
        ):
            excerpts[rel] = redacted[:2000]

    extractors = run_extractors(root, rels)
    summaries = hierarchical_summaries(
        files=rels,
        languages=languages,
        symbols=symbols,
        extractors=extractors,
    )

    return AnalysisResult(
        root=str(root),
        files=rels,
        tree=build_tree_lines(root, files),
        languages=languages,
        symbols=symbols,
        redacted_excerpts=excerpts,
        secret_findings_count=secret_count,
        ignored_files=ignored,
        extractors=extractors,
        summaries=summaries,
    )

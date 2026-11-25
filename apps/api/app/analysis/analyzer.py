"""Basic repository analyzer: file tree, languages, symbols."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.analysis.languages import detect_language, summarize_languages
from app.analysis.symbols import Symbol, extract_symbols
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


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        files.append(path)
        if len(files) >= MAX_FILES:
            break
    return files


def build_tree_lines(root: Path, files: list[Path]) -> list[str]:
    lines: list[str] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        lines.append(rel)
    return lines


def analyze_repository(root: Path) -> AnalysisResult:
    root = root.resolve()
    files = _iter_files(root)
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
        redacted, findings = redact_text(text)
        secret_count += len(findings)
        symbols.extend(extract_symbols(rel, redacted, lang))
        if lang in {"Python", "JavaScript", "TypeScript", "Markdown", "Go", "Rust"} or rel.endswith(
            ("README.md", "pyproject.toml", "package.json")
        ):
            excerpts[rel] = redacted[:2000]

    return AnalysisResult(
        root=str(root),
        files=rels,
        tree=build_tree_lines(root, files),
        languages=languages,
        symbols=symbols,
        redacted_excerpts=excerpts,
        secret_findings_count=secret_count,
    )

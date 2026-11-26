"""Hierarchical summarization basics — file → directory → repo (deterministic)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any


def hierarchical_summaries(
    *,
    files: list[str],
    languages: dict[str, int],
    symbols: list[Any],
    extractors: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build deterministic rollups without an LLM."""
    by_dir: dict[str, list[str]] = defaultdict(list)
    for rel in files:
        parent = str(Path(rel).parent)
        if parent == ".":
            parent = "(root)"
        by_dir[parent].append(rel)

    dir_summaries: list[dict[str, Any]] = []
    for directory, kids in sorted(by_dir.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:40]:
        dir_summaries.append(
            {
                "path": directory,
                "file_count": len(kids),
                "sample_files": kids[:8],
                "summary": f"{directory}: {len(kids)} files",
            }
        )

    symbol_names = []
    for sym in symbols[:50]:
        name = getattr(sym, "name", None) or (sym.get("name") if isinstance(sym, dict) else None)
        if name:
            symbol_names.append(str(name))

    extractors = extractors or {}
    endpoints = (extractors.get("openapi") or {}).get("endpoints") or []
    packages = (extractors.get("dependencies") or {}).get("packages") or []
    env_keys = (extractors.get("env_keys") or {}).get("keys") or []

    lang_bits = ", ".join(
        f"{k}={v}" for k, v in sorted(languages.items(), key=lambda x: -x[1])[:6]
    ) or "unknown"
    repo_summary = (
        f"Repository with {len(files)} files across {len(by_dir)} directories. "
        f"Languages: {lang_bits}. "
        f"Tracked symbols: {len(symbols)}. "
        f"OpenAPI endpoints: {len(endpoints)}. "
        f"Declared packages: {len(packages)}. "
        f"Env keys (examples only): {len(env_keys)}."
    )

    return {
        "repo": {"summary": repo_summary, "top_symbols": symbol_names[:20]},
        "directories": dir_summaries,
        "files": [
            {"path": rel, "summary": f"File {rel} ({Path(rel).suffix or 'no-ext'})"}
            for rel in files[:60]
        ],
    }

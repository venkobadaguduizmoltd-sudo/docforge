"""Build section citations from analyzer symbols at a pinned commit."""

from __future__ import annotations

from typing import Any


def citations_from_analysis(
    analysis: dict[str, Any],
    *,
    commit_sha: str | None,
    section_id: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Pick stable file+line citations for a section from analysis symbols/files.

    Heuristic: rotate through symbols by section_id hash so sections get distinct
    but deterministic citations without inventing paths.
    """
    symbols = analysis.get("symbols") or []
    files = analysis.get("files") or []
    if not symbols and not files:
        return []

    seed = sum(ord(c) for c in section_id) or 1
    citations: list[dict[str, Any]] = []

    if symbols:
        start = seed % len(symbols)
        for offset in range(min(limit, len(symbols))):
            sym = symbols[(start + offset) % len(symbols)]
            if isinstance(sym, dict):
                citations.append(
                    {
                        "file": sym.get("path") or sym.get("file") or "",
                        "line": sym.get("line"),
                        "end_line": sym.get("line"),
                        "commit_sha": commit_sha,
                        "symbol": sym.get("name"),
                    }
                )
    elif files:
        start = seed % len(files)
        for offset in range(min(limit, len(files))):
            path = files[(start + offset) % len(files)]
            citations.append(
                {
                    "file": path,
                    "line": 1,
                    "end_line": None,
                    "commit_sha": commit_sha,
                    "symbol": None,
                }
            )

    return [c for c in citations if c.get("file")]

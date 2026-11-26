"""Deterministic OpenAPI / Swagger path + method extraction."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_CANDIDATE_NAMES = (
    "openapi.json",
    "openapi.yaml",
    "openapi.yml",
    "swagger.json",
    "swagger.yaml",
    "swagger.yml",
)


def extract_openapi(root: Path, files: list[str]) -> dict[str, Any]:
    endpoints: list[dict[str, str]] = []
    sources: list[str] = []
    for rel in files:
        name = Path(rel).name.lower()
        if name not in _CANDIDATE_NAMES and "/openapi." not in rel.lower():
            continue
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        sources.append(rel)
        endpoints.extend(_parse_openapi_text(text))
    # Deduplicate
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for item in endpoints:
        key = (item["method"], item["path"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return {"sources": sources, "endpoints": unique[:200]}


def _parse_openapi_text(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    # JSON first
    try:
        data = json.loads(text)
        paths = data.get("paths") or {}
        if isinstance(paths, dict):
            for path, methods in paths.items():
                if not isinstance(methods, dict):
                    continue
                for method in methods:
                    if method.lower() in {"get", "post", "put", "patch", "delete", "head", "options"}:
                        out.append({"method": method.upper(), "path": str(path)})
            return out
    except json.JSONDecodeError:
        pass
    # Lightweight YAML path scan (no PyYAML dependency required for paths block)
    for match in re.finditer(
        r"^(\s*)(/[^\s:]+):\s*$",
        text,
        flags=re.MULTILINE,
    ):
        path = match.group(2)
        # Look ahead a few lines for methods
        start = match.end()
        chunk = text[start : start + 400]
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            if re.search(rf"^\s+{method}\s*:", chunk, flags=re.MULTILINE | re.IGNORECASE):
                out.append({"method": method.upper(), "path": path})
    return out

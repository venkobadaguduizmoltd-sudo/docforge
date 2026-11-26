"""Deterministic dependency manifest extractors (package.json, pyproject, requirements)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def extract_dependencies(root: Path, files: list[str]) -> dict[str, Any]:
    packages: list[dict[str, str]] = []
    sources: list[str] = []
    for rel in files:
        name = Path(rel).name.lower()
        path = root / rel
        if not path.is_file():
            continue
        if name == "package.json":
            sources.append(rel)
            packages.extend(_from_package_json(path))
        elif name == "pyproject.toml":
            sources.append(rel)
            packages.extend(_from_pyproject(path))
        elif name.startswith("requirements") and name.endswith(".txt"):
            sources.append(rel)
            packages.extend(_from_requirements(path))
    # Dedup by name
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for pkg in packages:
        key = f"{pkg['ecosystem']}:{pkg['name']}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(pkg)
    return {"sources": sources, "packages": unique[:300]}


def _from_package_json(path: Path) -> list[dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    out: list[dict[str, str]] = []
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        block = data.get(section) or {}
        if not isinstance(block, dict):
            continue
        for name, version in block.items():
            out.append(
                {
                    "ecosystem": "npm",
                    "name": str(name),
                    "version": str(version),
                    "section": section,
                }
            )
    return out


def _from_pyproject(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: list[dict[str, str]] = []
    # Very small TOML subset: poetry/project dependencies lines `"pkg = ..."` or `pkg = "..."`
    for match in re.finditer(
        r'^\s*(?:\"([^\"]+)\"|([A-Za-z0-9_.\-]+))\s*=\s*\"([^\"]*)\"',
        text,
        flags=re.MULTILINE,
    ):
        name = match.group(1) or match.group(2)
        if name in {"name", "version", "description", "readme", "requires-python"}:
            continue
        out.append({"ecosystem": "pypi", "name": name, "version": match.group(3), "section": "pyproject"})
    return out


def _from_requirements(path: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        name = re.split(r"[<>=\[]", stripped, maxsplit=1)[0].strip()
        if name:
            out.append({"ecosystem": "pypi", "name": name, "version": "", "section": path.name})
    return out

"""Extract env key names from .env.example / sample env files (never values)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def extract_env_keys(root: Path, files: list[str]) -> dict[str, Any]:
    keys: set[str] = set()
    sources: list[str] = []
    for rel in files:
        name = Path(rel).name
        if name not in {".env.example", ".env.sample", ".env.template"} and not name.endswith(
            ".env.example"
        ):
            continue
        path = root / rel
        if not path.is_file():
            continue
        sources.append(rel)
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key = stripped.split("=", 1)[0].strip()
            if _ENV_NAME_RE.match(key):
                keys.add(key)
    return {"sources": sources, "keys": sorted(keys)}

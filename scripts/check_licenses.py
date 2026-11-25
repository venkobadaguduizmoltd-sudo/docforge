#!/usr/bin/env python3
"""Fail CI when declared dependencies use disallowed license classes.

Phase 0 uses a curated allowlist keyed by package name. Extend ALLOWED when
adding OSI/self-hostable packages; never add commercial-only required deps.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# package -> OSI/free license id used for policy checks
ALLOWED: dict[str, str] = {
    "fastapi": "MIT",
    "uvicorn": "BSD-3-Clause",
    "sqlalchemy": "MIT",
    "alembic": "MIT",
    "pydantic": "MIT",
    "pydantic-settings": "MIT",
    "email-validator": "MIT",
    "psycopg": "LGPL-3.0",
    "python-jose": "MIT",
    "passlib": "BSD-3-Clause",
    "bcrypt": "Apache-2.0",
    "python-multipart": "Apache-2.0",
    "httpx": "BSD-3-Clause",
    "arq": "MIT",
    "redis": "MIT",
    "pytest": "MIT",
    "pytest-asyncio": "Apache-2.0",
    "ruff": "MIT",
    "mypy": "MIT",
    "types-passlib": "Apache-2.0",
    "react": "MIT",
    "react-dom": "MIT",
    "react-router-dom": "MIT",
    "@tanstack/react-query": "MIT",
    "vite": "MIT",
    "typescript": "Apache-2.0",
    "tailwindcss": "MIT",
    "autoprefixer": "MIT",
    "postcss": "MIT",
    "vitest": "MIT",
    "eslint": "MIT",
    "typescript-eslint": "MIT",
    "@vitejs/plugin-react": "MIT",
    "@types/react": "MIT",
    "@types/react-dom": "MIT",
    "@types/node": "MIT",
    "@eslint/js": "MIT",
    "jinja2": "BSD-3-Clause",
    "python-docx": "MIT",
    "reportlab": "BSD-3-Clause",
    "tree-sitter": "MIT",
    "tree-sitter-python": "MIT",
}

# Simulated commercial-only / non-OSI markers that must never appear
DISALLOWED_MARKERS = {
    "openai-official-proprietary-sdk": "Commercial-Only",
    "closed-source-llm-runtime": "Proprietary",
    "acme-enterprise-only": "Commercial-Only",
}


def parse_python_requirements(path: Path) -> list[str]:
    names: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[<>=\[]", line, maxsplit=1)[0].strip().lower()
        names.append(name)
    return names


def parse_npm_dependencies(path: Path) -> list[str]:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for section in ("dependencies", "devDependencies"):
        names.extend(data.get(section, {}).keys())
    return names


def main() -> int:
    errors: list[str] = []
    packages: list[str] = []

    packages.extend(parse_python_requirements(ROOT / "apps/api/requirements.txt"))
    packages.extend(parse_python_requirements(ROOT / "apps/worker/requirements.txt"))
    packages.extend(parse_npm_dependencies(ROOT / "apps/web/package.json"))

    for name in packages:
        key = name.lower()
        if key in DISALLOWED_MARKERS:
            errors.append(f"{name}: disallowed license {DISALLOWED_MARKERS[key]}")
            continue
        if key not in ALLOWED and name not in ALLOWED:
            errors.append(f"{name}: not in Phase 0 license allowlist — update docs/LICENSES.md and ALLOWED")
            continue

    # Explicit self-test: commercial-only markers always fail if introduced
    for marker, license_name in DISALLOWED_MARKERS.items():
        if marker in packages:
            errors.append(f"{marker}: {license_name} is not allowed")

    if errors:
        print("License check FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"License check OK ({len(packages)} packages allowlisted).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

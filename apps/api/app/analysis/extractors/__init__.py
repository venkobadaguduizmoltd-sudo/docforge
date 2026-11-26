"""Deterministic extractors — OpenAPI, env samples, dependency manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.analysis.extractors.deps import extract_dependencies
from app.analysis.extractors.env_files import extract_env_keys
from app.analysis.extractors.openapi import extract_openapi


def run_extractors(root: Path, files: list[str]) -> dict[str, Any]:
    return {
        "openapi": extract_openapi(root, files),
        "env_keys": extract_env_keys(root, files),
        "dependencies": extract_dependencies(root, files),
    }

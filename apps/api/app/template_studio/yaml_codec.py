"""YAML ↔ JSON helpers for raw template specs."""

from __future__ import annotations

from typing import Any

import yaml

from app.template_studio.schema import validate_template_spec


def spec_from_yaml(text: str) -> dict[str, Any]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping/object")
    return validate_template_spec(data)


def spec_to_yaml(spec: dict[str, Any]) -> str:
    return yaml.safe_dump(spec, sort_keys=False, allow_unicode=True)

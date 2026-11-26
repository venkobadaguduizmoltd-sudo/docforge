"""JSON Schema for immutable template structure specs."""

from __future__ import annotations

from typing import Any

import jsonschema

TEMPLATE_STRUCTURE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://docforge.local/schemas/template-structure.json",
    "title": "DocForgeTemplateStructure",
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "name", "slug", "sections"],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "slug": {
            "type": "string",
            "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$",
            "minLength": 1,
            "maxLength": 128,
        },
        "description": {"type": "string"},
        "tags": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "uniqueItems": True,
        },
        "theme": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "html": {"type": "string"},
                "css": {"type": "string"},
                "docx": {"type": "string"},
                "logo": {"type": "string"},
                "fonts": {"type": "array", "items": {"type": "string"}},
            },
        },
        "assets": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "Relative paths for logo/fonts/CSS extras (Phase 4).",
        },
        "sections": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "title"],
                "properties": {
                    "id": {
                        "type": "string",
                        "pattern": "^[a-z][a-z0-9_]{0,63}$",
                    },
                    "title": {"type": "string", "minLength": 1},
                    "description": {"type": "string"},
                    "instructions": {
                        "type": "string",
                        "description": "Authoring / generation instructions for this section.",
                    },
                    "content_schema": {
                        "type": "object",
                        "description": "Optional JSON Schema fragment for section content.",
                    },
                },
            },
        },
    },
}


class TemplateSpecValidationError(ValueError):
    """Raised when a template structure spec fails JSON Schema validation."""


def validate_template_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Validate and return the spec (unchanged) or raise TemplateSpecValidationError."""
    validator = jsonschema.Draft202012Validator(TEMPLATE_STRUCTURE_SCHEMA)
    errors = sorted(validator.iter_errors(spec), key=lambda e: list(e.path))
    if errors:
        messages = [f"{'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}" for err in errors]
        raise TemplateSpecValidationError("; ".join(messages[:8]))
    section_ids = [s["id"] for s in spec["sections"]]
    if len(section_ids) != len(set(section_ids)):
        raise TemplateSpecValidationError("section ids must be unique")
    return spec

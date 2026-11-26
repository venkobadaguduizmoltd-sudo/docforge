"""Theme tokens for diagram rendering — keep LLM away from raw style strings."""

from __future__ import annotations

THEME_TOKENS: dict[str, str] = {
    "ink": "#16201c",
    "muted": "#5a6c62",
    "accent": "#0f766e",
    "canvas": "#f4f6f1",
    "border": "#d2dcd6",
    "danger": "#b91c1c",
    "font": "IBM Plex Sans",
}


def resolve_token(name: str, default: str | None = None) -> str:
    return THEME_TOKENS.get(name, default or THEME_TOKENS["ink"])

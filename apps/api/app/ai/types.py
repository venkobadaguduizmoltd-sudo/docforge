"""Shared types for DocGenProvider adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ProviderKind(StrEnum):
    MODEL = "model"
    AGENT = "agent"


@dataclass(slots=True)
class CompleteRequest:
    system: str
    user: str
    model: str | None = None
    temperature: float = 0.2
    max_tokens: int | None = None
    response_json: bool = True
    # When True (agent kind default), adapters must not pull retrieval/RAG context.
    skip_retrieval: bool = False
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CompleteResponse:
    text: str
    model: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModelInfo:
    id: str
    name: str | None = None
    owned_by: str | None = None


@dataclass(slots=True)
class TestResult:
    ok: bool
    latency_ms: float
    message: str
    models_sample: list[str] = field(default_factory=list)

"""DocGenProvider interface — model and agent backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.ai.types import (
    CompleteRequest,
    CompleteResponse,
    ModelInfo,
    ProviderKind,
    TestResult,
)


class DocGenProvider(ABC):
    """Unified AI backend contract for DocForge generation and admin tooling."""

    name: str
    kind: ProviderKind
    adapter_type: str

    @abstractmethod
    async def complete(self, request: CompleteRequest) -> CompleteResponse:
        """Generate a completion. Raises ProviderError on failure."""

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """List available models (may be empty for agent adapters)."""

    @abstractmethod
    async def test_connection(self) -> TestResult:
        """Lightweight connectivity / auth check."""

    async def cancel(self, handle: Any | None = None) -> None:
        """Best-effort cancel of an in-flight request. Default is a no-op."""
        return None

    @property
    def skips_retrieval(self) -> bool:
        """Agent providers skip retrieval by product policy."""
        return self.kind == ProviderKind.AGENT

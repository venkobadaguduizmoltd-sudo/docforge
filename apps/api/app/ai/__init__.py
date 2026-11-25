"""Phase 3 — DocGen AI provider abstraction and adapters."""

from app.ai.errors import ProviderError, ProviderErrorCode
from app.ai.protocol import DocGenProvider
from app.ai.types import (
    CompleteRequest,
    CompleteResponse,
    ModelInfo,
    ProviderKind,
    TestResult,
)

__all__ = [
    "CompleteRequest",
    "CompleteResponse",
    "DocGenProvider",
    "ModelInfo",
    "ProviderError",
    "ProviderErrorCode",
    "ProviderKind",
    "TestResult",
]

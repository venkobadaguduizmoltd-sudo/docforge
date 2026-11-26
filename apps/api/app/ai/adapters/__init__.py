"""Concrete DocGenProvider adapters."""

from app.ai.adapters.anthropic import AnthropicProvider
from app.ai.adapters.azure_openai import AzureOpenAIProvider
from app.ai.adapters.bedrock import BedrockProvider
from app.ai.adapters.cursor_cli import CursorCLIProvider
from app.ai.adapters.gemini import GeminiProvider
from app.ai.adapters.mock import MockProvider
from app.ai.adapters.openai import OpenAIProvider
from app.ai.adapters.openai_compatible import OpenAICompatibleProvider

ADAPTER_TYPES: dict[str, type] = {
    "mock": MockProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "ollama": OpenAICompatibleProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "azure_openai": AzureOpenAIProvider,
    "gemini": GeminiProvider,
    "vertex": GeminiProvider,
    "bedrock": BedrockProvider,
    "cursor_cli": CursorCLIProvider,
}

__all__ = [
    "ADAPTER_TYPES",
    "AnthropicProvider",
    "AzureOpenAIProvider",
    "BedrockProvider",
    "CursorCLIProvider",
    "GeminiProvider",
    "MockProvider",
    "OpenAICompatibleProvider",
    "OpenAIProvider",
]

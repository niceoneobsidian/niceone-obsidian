"""Configuration-driven registration of optional cloud LLM providers."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from ois.runtime.cloud_llm import (
    AnthropicProvider,
    GeminiProvider,
    OpenAIProvider,
    ProviderConfigurationError,
)
from ois.runtime.fabrics import InMemoryLLMGateway


def _is_enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def register_configured_cloud_providers(gateway: InMemoryLLMGateway) -> tuple[str, ...]:
    """Register only explicitly enabled providers, validating credentials first."""
    configurations: tuple[tuple[str, str, tuple[str, ...], Callable[[], Any]], ...] = (
        ("openai", "OPENAI_ENABLED", ("OPENAI_API_KEY",), OpenAIProvider),
        ("anthropic", "ANTHROPIC_ENABLED", ("ANTHROPIC_API_KEY",), AnthropicProvider),
        ("gemini", "GEMINI_ENABLED", ("GEMINI_API_KEY", "GOOGLE_API_KEY"), GeminiProvider),
    )
    registered: list[str] = []
    for provider_id, enabled_var, credential_vars, factory in configurations:
        if not _is_enabled(enabled_var):
            continue
        if not any(os.getenv(name, "").strip() for name in credential_vars):
            raise ProviderConfigurationError(
                f"{enabled_var}=true requires {' or '.join(credential_vars)}"
            )
        provider = factory()
        gateway.register_provider(provider_id, provider.invoke)
        registered.append(provider_id)
    return tuple(registered)

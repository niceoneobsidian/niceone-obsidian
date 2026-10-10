"""Optional cloud LLM provider adapters with lazy SDK imports.

Install the provider extra and set its credential before enabling a provider.
"""

from __future__ import annotations

import os
from typing import Any


class ProviderConfigurationError(ValueError):
    """Raised when an explicitly enabled provider is not configured."""


class OpenAIProvider:
    provider_id = "openai"

    def __init__(self) -> None:
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise ProviderConfigurationError("Set OPENAI_API_KEY to configure OpenAI")

    def invoke(self, model: str, request: dict[str, Any]) -> dict[str, Any]:
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ProviderConfigurationError(
                "OpenAI provider requires the 'openai' package; install the cloud-llm extra"
            ) from exc
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.responses.create(model=model, input=request.get("prompt", ""))
        usage = getattr(response, "usage", None)
        return {
            "response": response.output_text,
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        }


class AnthropicProvider:
    provider_id = "anthropic"

    def __init__(self) -> None:
        if not os.getenv("ANTHROPIC_API_KEY", "").strip():
            raise ProviderConfigurationError("Set ANTHROPIC_API_KEY to configure Anthropic")

    def invoke(self, model: str, request: dict[str, Any]) -> dict[str, Any]:
        try:
            from anthropic import Anthropic  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ProviderConfigurationError(
                "Anthropic provider requires the 'anthropic' package; install the cloud-llm extra"
            ) from exc
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=model,
            max_tokens=int(request.get("max_tokens", 1024)),
            messages=[{"role": "user", "content": request.get("prompt", "")}],
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        usage = response.usage
        return {
            "response": text,
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        }


class GeminiProvider:
    provider_id = "gemini"

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv(
            "GOOGLE_API_KEY", ""
        ).strip()
        if not self.api_key:
            raise ProviderConfigurationError(
                "Set GEMINI_API_KEY or GOOGLE_API_KEY to configure Gemini"
            )

    def invoke(self, model: str, request: dict[str, Any]) -> dict[str, Any]:
        try:
            from google import genai  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ProviderConfigurationError(
                "Gemini provider requires the 'google-genai' package; install the cloud-llm extra"
            ) from exc
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(model=model, contents=request.get("prompt", ""))
        usage = getattr(response, "usage_metadata", None)
        return {
            "response": response.text or "",
            "input_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
        }

"""Optional cloud LLM adapters for the canonical OIS gateway.

Install with ``pip install -e '.[cloud-llm]'``. SDK imports are lazy so
Ollama-only and offline installations do not need cloud SDK dependencies.
"""

from __future__ import annotations

import os
from typing import Any


class ProviderConfigurationError(RuntimeError):
    """A provider is not configured; retrying with another vendor is unsafe."""

    fallback_allowed = False


class ProviderCallError(RuntimeError):
    """Sanitized provider failure with an explicit fallback decision."""

    def __init__(self, provider: str, error_type: str, *, fallback_allowed: bool) -> None:
        super().__init__(f"{provider} request failed ({error_type})")
        self.fallback_allowed = fallback_allowed


def _fallback_for_sdk_error(exc: Exception) -> bool:
    """Permit fallback for transient failures, not auth, request, or policy errors."""
    name = type(exc).__name__.lower()
    status = getattr(exc, "status_code", None)
    blocked_names = (
        "authentication",
        "permission",
        "forbidden",
        "unauthorized",
        "invalidrequest",
        "badrequest",
        "contentpolicy",
        "policyviolation",
    )
    if any(token in name for token in blocked_names):
        return False
    return status not in {400, 401, 403, 404, 422}


class OpenAIProvider:
    """OpenAI Responses API adapter; requires the optional ``openai`` package."""

    provider_id = "openai"

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            if not os.getenv("OPENAI_API_KEY"):
                raise ProviderConfigurationError("Set OPENAI_API_KEY to configure OpenAI")
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ProviderConfigurationError(
                    "OpenAI SDK missing; install the cloud-llm extra"
                ) from exc
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.client = client

    def invoke(self, model: str, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request.get("prompt", "")
        options = request.get("openai_options")
        options = options if isinstance(options, dict) else {}
        kwargs: dict[str, Any] = {"model": model, "input": prompt}
        for key in ("instructions", "max_output_tokens", "temperature", "top_p"):
            if key in options:
                kwargs[key] = options[key]
        try:
            result = self.client.responses.create(**kwargs)
        except Exception as exc:
            raise ProviderCallError(
                self.provider_id,
                type(exc).__name__,
                fallback_allowed=_fallback_for_sdk_error(exc),
            ) from exc
        usage = getattr(result, "usage", None)
        return {
            "response": getattr(result, "output_text", "") or "",
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        }


class AnthropicProvider:
    """Anthropic Messages API adapter; requires the optional ``anthropic`` package."""

    provider_id = "anthropic"

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise ProviderConfigurationError("Set ANTHROPIC_API_KEY to configure Anthropic")
            try:
                from anthropic import Anthropic
            except ImportError as exc:
                raise ProviderConfigurationError(
                    "Anthropic SDK missing; install the cloud-llm extra"
                ) from exc
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.client = client

    def invoke(self, model: str, request: dict[str, Any]) -> dict[str, Any]:
        options = request.get("anthropic_options")
        options = options if isinstance(options, dict) else {}
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": options.get("max_tokens", 1024),
            "messages": [{"role": "user", "content": request.get("prompt", "")}],
        }
        for key in ("system", "temperature", "top_p", "top_k", "stop_sequences"):
            if key in options:
                kwargs[key] = options[key]
        try:
            result = self.client.messages.create(**kwargs)
        except Exception as exc:
            raise ProviderCallError(
                self.provider_id,
                type(exc).__name__,
                fallback_allowed=_fallback_for_sdk_error(exc),
            ) from exc
        content = getattr(result, "content", [])
        text = "".join(
            getattr(block, "text", "")
            for block in content
            if isinstance(getattr(block, "text", None), str)
        )
        usage = getattr(result, "usage", None)
        return {
            "response": text,
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        }


class GeminiProvider:
    """Google Gemini adapter using the Google Gen AI SDK."""

    provider_id = "gemini"

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ProviderConfigurationError(
                    "Set GEMINI_API_KEY or GOOGLE_API_KEY to configure Gemini"
                )
            try:
                from google import genai
            except ImportError as exc:
                raise ProviderConfigurationError(
                    "Google Gen AI SDK missing; install the cloud-llm extra"
                ) from exc
            client = genai.Client(api_key=api_key)
        self.client = client

    def invoke(self, model: str, request: dict[str, Any]) -> dict[str, Any]:
        options = request.get("gemini_options")
        options = options if isinstance(options, dict) else {}
        config: dict[str, Any] = {}
        for key in (
            "system_instruction",
            "temperature",
            "top_p",
            "top_k",
            "max_output_tokens",
            "stop_sequences",
            "response_mime_type",
        ):
            if key in options:
                config[key] = options[key]
        kwargs: dict[str, Any] = {"model": model, "contents": request.get("prompt", "")}
        if config:
            kwargs["config"] = config
        try:
            result = self.client.models.generate_content(**kwargs)
        except Exception as exc:
            raise ProviderCallError(
                self.provider_id,
                type(exc).__name__,
                fallback_allowed=_fallback_for_sdk_error(exc),
            ) from exc
        usage = getattr(result, "usage_metadata", None)
        return {
            "response": getattr(result, "text", "") or "",
            "input_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
        }

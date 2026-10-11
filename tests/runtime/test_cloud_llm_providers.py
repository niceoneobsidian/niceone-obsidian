from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from ois.architecture.fabrics import LLMGatewaySpec, ModelRoute
from ois.runtime.cloud_llm import (
    AnthropicProvider,
    GeminiProvider,
    OpenAIProvider,
    ProviderCallError,
    ProviderConfigurationError,
)
from ois.runtime.llm_gateway import LLMGateway


class _OpenAIResponses:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.result


class _AnthropicMessages:
    def __init__(self, result: Any = None) -> None:
        self.result = result
        self.kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self.result


class _GeminiModels:
    def __init__(self, result: Any = None) -> None:
        self.result = result
        self.kwargs: dict[str, Any] | None = None

    def generate_content(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self.result


def test_openai_adapter_normalizes_response_and_usage() -> None:
    responses = _OpenAIResponses(
        SimpleNamespace(
            output_text="hello",
            usage=SimpleNamespace(input_tokens=11, output_tokens=7),
        )
    )
    provider = OpenAIProvider(client=SimpleNamespace(responses=responses))
    result = provider.invoke(
        "gpt-4.1-mini", {"prompt": "hello", "openai_options": {"temperature": 0}}
    )
    assert result == {"response": "hello", "input_tokens": 11, "output_tokens": 7}
    assert responses.kwargs == {"model": "gpt-4.1-mini", "input": "hello", "temperature": 0}


def test_anthropic_adapter_normalizes_text_and_usage() -> None:
    messages = _AnthropicMessages(
        SimpleNamespace(
            content=[SimpleNamespace(text="hello")],
            usage=SimpleNamespace(input_tokens=9, output_tokens=4),
        )
    )
    provider = AnthropicProvider(client=SimpleNamespace(messages=messages))
    result = provider.invoke("claude-sonnet", {"prompt": "hello"})
    assert result == {"response": "hello", "input_tokens": 9, "output_tokens": 4}
    assert messages.kwargs is not None
    assert messages.kwargs["messages"] == [{"role": "user", "content": "hello"}]
    assert messages.kwargs["max_tokens"] == 1024


def test_gemini_adapter_normalizes_text_and_usage() -> None:
    models = _GeminiModels(
        SimpleNamespace(
            text="hello",
            usage_metadata=SimpleNamespace(prompt_token_count=8, candidates_token_count=3),
        )
    )
    provider = GeminiProvider(client=SimpleNamespace(models=models))
    result = provider.invoke(
        "gemini-2.5-flash", {"prompt": "hello", "gemini_options": {"temperature": 0}}
    )
    assert result == {"response": "hello", "input_tokens": 8, "output_tokens": 3}
    assert models.kwargs == {
        "model": "gemini-2.5-flash",
        "contents": "hello",
        "config": {"temperature": 0},
    }


def test_gateway_does_not_fallback_after_authentication_failure() -> None:
    gateway = LLMGateway(
        spec=LLMGatewaySpec(ref_id="cloud-models", fallback_policy="next_compatible")
    )
    gateway.register_route(
        ModelRoute(
            ref_id="primary",
            provider="openai",
            model="gpt-4.1-mini",
            capabilities=("text",),
            cost_profile={"cloud": 0},
        )
    )
    gateway.register_route(
        ModelRoute(
            ref_id="backup",
            provider="anthropic",
            model="claude-sonnet",
            capabilities=("text",),
            cost_profile={"cloud": 1},
        )
    )
    calls: list[str] = []

    def primary(model: str, request: dict[str, Any]) -> Any:
        calls.append("openai")
        raise ProviderCallError("openai", "AuthenticationError", fallback_allowed=False)

    def backup(model: str, request: dict[str, Any]) -> Any:
        calls.append("anthropic")
        return {"response": "should not be reached"}

    class _Provider:
        def __init__(self, provider_id: str, callback: Any) -> None:
            self.provider_id = provider_id
            self.callback = callback

        def invoke(self, model: str, request: dict[str, Any]) -> Any:
            return self.callback(model, request)

    gateway.register_provider(_Provider("openai", primary))
    gateway.register_provider(_Provider("anthropic", backup))
    with pytest.raises(ProviderCallError):
        gateway.invoke("request-1", "sensitive prompt", capabilities={"text"})
    assert calls == ["openai"]
    assert gateway.records[0].status == "failed"


def test_provider_call_error_does_not_expose_original_message() -> None:
    error = ProviderCallError("openai", "AuthenticationError", fallback_allowed=False)
    assert "api_key" not in str(error).lower()
    assert "AuthenticationError" in str(error)


def test_missing_gemini_key_is_configuration_error(monkeypatch: Any) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ProviderConfigurationError):
        GeminiProvider()

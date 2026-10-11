from __future__ import annotations

from typing import Any

import pytest

import ois.runtime.cloud_provider_setup as setup
from ois.architecture.fabrics import LLMGatewaySpec
from ois.runtime.cloud_llm import ProviderConfigurationError
from ois.runtime.fabrics import FabricRuntime


class _FakeProvider:
    def invoke(self, model: str, request: dict[str, Any]) -> dict[str, str]:
        return {"response": f"{model}:{request.get('prompt', '')}"}


def _gateway():
    runtime = FabricRuntime()
    return runtime.configure_gateway(LLMGatewaySpec(ref_id="cloud-registration-test"))


def test_disabled_cloud_providers_are_not_registered(monkeypatch: Any) -> None:
    for name in (
        "OPENAI_ENABLED",
        "ANTHROPIC_ENABLED",
        "GEMINI_ENABLED",
    ):
        monkeypatch.setenv(name, "false")

    gateway = _gateway()

    assert setup.register_configured_cloud_providers(gateway) == ()
    assert gateway.providers == {}


def test_enabled_openai_without_key_fails_clearly(monkeypatch: Any) -> None:
    monkeypatch.setenv("OPENAI_ENABLED", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        setup.register_configured_cloud_providers(_gateway())


def test_enabled_providers_register_without_real_api_calls(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("OPENAI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("ANTHROPIC_ENABLED", "false")
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.setattr(setup, "OpenAIProvider", _FakeProvider)

    gateway = _gateway()

    assert setup.register_configured_cloud_providers(gateway) == ("openai",)
    assert gateway.providers["openai"]("test-model", {"prompt": "hello"}) == {
        "response": "test-model:hello"
    }

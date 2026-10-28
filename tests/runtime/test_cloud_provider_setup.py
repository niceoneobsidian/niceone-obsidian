from __future__ import annotations

from typing import Any

import pytest

from ois.architecture.fabrics import LLMGatewaySpec
from ois.runtime import cloud_provider_setup as setup
from ois.runtime.cloud_llm import ProviderConfigurationError
from ois.runtime.fabrics import FabricRuntime


class FakeProvider:
    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id

    def invoke(self, model: str, request: dict[str, Any]) -> dict[str, str]:
        return {"response": f"{self.provider_id}:{model}"}


def test_cloud_providers_are_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "OPENAI_ENABLED",
        "OPENAI_API_KEY",
        "ANTHROPIC_ENABLED",
        "ANTHROPIC_API_KEY",
        "GEMINI_ENABLED",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    gateway = FabricRuntime().configure_gateway(LLMGatewaySpec(ref_id="test"))
    assert gateway.providers == {}


def test_only_explicitly_enabled_providers_register(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_ENABLED", "false")
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    monkeypatch.setattr(setup, "OpenAIProvider", lambda: FakeProvider("openai"))
    gateway = FabricRuntime().configure_gateway(
        LLMGatewaySpec(ref_id="test", providers=("openai",)),
        register_cloud_providers=False,
    )
    assert setup.register_configured_cloud_providers(gateway) == ("openai",)
    assert gateway.providers["openai"]("model", {"prompt": "hello"}) == {"response": "openai:model"}


@pytest.mark.parametrize(
    ("enabled", "credential"),
    [
        ("OPENAI_ENABLED", "OPENAI_API_KEY"),
        ("ANTHROPIC_ENABLED", "ANTHROPIC_API_KEY"),
        ("GEMINI_ENABLED", "GEMINI_API_KEY"),
    ],
)
def test_enabled_provider_requires_credentials(
    monkeypatch: pytest.MonkeyPatch, enabled: str, credential: str
) -> None:
    monkeypatch.setenv(enabled, "true")
    monkeypatch.delenv(credential, raising=False)
    with pytest.raises(ProviderConfigurationError, match="requires"):
        setup.register_configured_cloud_providers(
            FabricRuntime().configure_gateway(
                LLMGatewaySpec(ref_id="test"),
                register_cloud_providers=False,
            )
        )


def test_gateway_initialization_calls_cloud_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        setup,
        "register_configured_cloud_providers",
        lambda gateway: calls.append(gateway) or (),
    )
    runtime = FabricRuntime()
    gateway = runtime.configure_gateway(LLMGatewaySpec(ref_id="auto"))
    assert calls == [gateway]


def test_gemini_accepts_google_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(setup, "GeminiProvider", lambda: FakeProvider("gemini"))
    gateway = FabricRuntime().configure_gateway(
        LLMGatewaySpec(ref_id="test"), register_cloud_providers=False
    )
    assert setup.register_configured_cloud_providers(gateway) == ("gemini",)

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import Request

import pytest

from ois.architecture.fabrics import LLMGatewaySpec, ModelRoute
from ois.runtime.llm_gateway import LLMGateway
from ois.runtime.ollama import OllamaProvider


class FakeResponse(BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _response(text: str) -> FakeResponse:
    return FakeResponse(json.dumps({"response": text, "done": True}).encode("utf-8"))


def test_ollama_provider_implements_generate_contract() -> None:
    captured: list[Request] = []

    def fake_urlopen(request: Request, *, timeout: float) -> FakeResponse:
        captured.append(request)
        return _response("hello from ollama")

    with patch("ois.runtime.ollama.urlopen", fake_urlopen):
        result = OllamaProvider(base_url="http://ollama:11434").invoke(
            "qwen3:8b",
            {"prompt": "hello", "ollama_options": {"temperature": 0}},
        )

    assert result["response"] == "hello from ollama"
    assert captured[0].full_url == "http://ollama:11434/api/generate"
    assert json.loads(captured[0].data or b"") == {
        "model": "qwen3:8b",
        "prompt": "hello",
        "stream": False,
        "options": {"temperature": 0},
    }


def _gateway() -> LLMGateway:
    gateway = LLMGateway(
        spec=LLMGatewaySpec(
            ref_id="local-models",
            providers=("ollama",),
            fallback_policy="next_compatible",
        )
    )
    gateway.register_provider(OllamaProvider(base_url="http://ollama:11434"))
    gateway.register_route(
        ModelRoute(
            ref_id="qwen3-local",
            provider="ollama",
            model="qwen3:8b",
            capabilities=("text",),
            cost_profile={"local": 0.0},
        )
    )
    gateway.register_route(
        ModelRoute(
            ref_id="deepseek-local",
            provider="ollama",
            model="deepseek-r1:8b",
            capabilities=("text",),
            cost_profile={"local": 1.0},
        )
    )
    return gateway


def test_gateway_executes_ollama_route_and_records_inference() -> None:
    def fake_urlopen(request: Request, *, timeout: float) -> FakeResponse:
        payload = json.loads(request.data or b"{}")
        assert payload["model"] == "qwen3:8b"
        return _response("OIS local model response")

    gateway = _gateway()
    with patch("ois.runtime.ollama.urlopen", fake_urlopen):
        result = gateway.invoke("request-1", "Explain OIS.", capabilities={"text"})

    assert result["response"] == "OIS local model response"
    assert len(gateway.records) == 1
    assert gateway.records[0].provider == "ollama"
    assert gateway.records[0].model == "qwen3:8b"
    assert gateway.records[0].status == "succeeded"


def test_gateway_falls_back_to_deepseek_when_qwen_fails() -> None:
    calls: list[str] = []

    def fake_urlopen(request: Request, *, timeout: float) -> FakeResponse:
        payload = json.loads(request.data or b"{}")
        model = payload["model"]
        calls.append(model)
        if model == "qwen3:8b":
            raise URLError("simulated local model failure")
        return _response("DeepSeek fallback response")

    gateway = _gateway()
    with patch("ois.runtime.ollama.urlopen", fake_urlopen):
        result = gateway.invoke("request-2", "Explain OIS.", capabilities={"text"})

    assert result["response"] == "DeepSeek fallback response"
    assert calls == ["qwen3:8b", "deepseek-r1:8b"]
    assert [record.status for record in gateway.records] == ["failed", "succeeded"]
    assert [record.model for record in gateway.records] == [
        "qwen3:8b",
        "deepseek-r1:8b",
    ]


def test_ollama_provider_surfaces_transport_timeout() -> None:
    def fake_urlopen(_request: Request, *, timeout: float) -> FakeResponse:
        assert timeout == 0.25
        raise URLError("simulated provider timeout")

    provider = OllamaProvider(base_url="http://ollama:11434", timeout=0.25)
    with patch("ois.runtime.ollama.urlopen", fake_urlopen):
        with pytest.raises(RuntimeError, match="Ollama request failed"):
            provider.invoke("qwen3:8b", {"prompt": "timeout test"})

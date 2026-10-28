from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from threading import Thread
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import Request

import pytest

from ois.architecture.fabrics import LLMGatewaySpec, ModelRoute
from ois.runtime.llm_gateway import (
    LLMGateway,
    ModelOutput,
    ModelOutputError,
    ModelProvidersExhausted,
    ModelProviderTimeout,
)
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

    assert result == ModelOutput("hello from ollama")
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

    assert result == ModelOutput("OIS local model response")
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

    assert result == ModelOutput("DeepSeek fallback response")
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
    with (
        patch("ois.runtime.ollama.urlopen", fake_urlopen),
        pytest.raises(RuntimeError, match="Ollama request failed"),
    ):
        provider.invoke("qwen3:8b", {"prompt": "timeout test"})
def test_ollama_rejects_malformed_model_output() -> None:
    with patch("ois.runtime.ollama.urlopen", lambda *_args, **_kwargs: _response("")):
        try:
            OllamaProvider(base_url="http://ollama:11434").invoke("qwen3:8b", {"prompt": "hello"})
        except ModelOutputError:
            pass
        else:
            raise AssertionError("empty model output must be rejected")


def test_command_like_model_text_remains_inert_output() -> None:
    command_text = "rm -rf /tmp/not-a-command"

    def fake_urlopen(request: Request, *, timeout: float) -> FakeResponse:
        return _response(command_text)

    gateway = _gateway()
    with patch("ois.runtime.ollama.urlopen", fake_urlopen):
        result = gateway.invoke("request-command-text", "Return a string", capabilities={"text"})

    assert result == ModelOutput(command_text)


def test_ollama_uses_validated_request_timeout() -> None:
    observed_timeouts: list[float] = []

    def fake_urlopen(request: Request, *, timeout: float) -> FakeResponse:
        observed_timeouts.append(timeout)
        return _response("bounded response")

    with patch("ois.runtime.ollama.urlopen", fake_urlopen):
        OllamaProvider(timeout=20).invoke(
            "qwen3:8b",
            {"prompt": "hello", "timeout_seconds": 0.25},
        )

    assert observed_timeouts == [0.25]


def test_ollama_enforces_request_timeout_on_loopback() -> None:
    class SlowHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            time.sleep(0.1)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"response":"late response"}')

        def log_message(self, *_args: object) -> None:
            return None

    server = HTTPServer(("127.0.0.1", 0), SlowHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider = OllamaProvider(base_url=f"http://127.0.0.1:{server.server_port}")
        try:
            provider.invoke("qwen3:8b", {"prompt": "hello", "timeout_seconds": 0.01})
        except ModelProviderTimeout as exc:
            assert "timed out" in str(exc)
        else:
            raise AssertionError("slow local response exceeded the configured timeout")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_ollama_rejects_invalid_request_timeout() -> None:
    provider = OllamaProvider()

    for timeout in (0, -1, float("inf"), True, "1"):
        try:
            provider.invoke("qwen3:8b", {"prompt": "hello", "timeout_seconds": timeout})
        except ValueError as exc:
            assert "timeout_seconds" in str(exc)
        else:
            raise AssertionError(f"invalid timeout accepted: {timeout!r}")


def test_gateway_reports_exhausted_provider_attempts() -> None:
    def failing_urlopen(request: Request, *, timeout: float) -> FakeResponse:
        raise URLError("simulated local timeout")

    gateway = _gateway()
    with patch("ois.runtime.ollama.urlopen", failing_urlopen):
        try:
            gateway.invoke("request-exhausted", "Explain OIS.", capabilities={"text"})
        except ModelProvidersExhausted as exc:
            assert exc.attempts == 2
            assert exc.last_error_type == "RuntimeError"
        else:
            raise AssertionError("provider exhaustion must be explicit")

    assert [record.status for record in gateway.records] == ["failed", "failed"]


def test_gateway_max_attempts_stops_fallback_early() -> None:
    calls: list[str] = []

    def failing_urlopen(request: Request, *, timeout: float) -> FakeResponse:
        model = json.loads(request.data or b"{}")["model"]
        calls.append(model)
        raise URLError("simulated provider failure")

    gateway = _gateway()
    gateway.max_attempts = 1
    with patch("ois.runtime.ollama.urlopen", failing_urlopen):
        try:
            gateway.invoke("request-attempt-cap", "Explain OIS.", capabilities={"text"})
        except ModelProvidersExhausted as exc:
            assert exc.attempts == 1
        else:
            raise AssertionError("gateway exceeded its configured provider-attempt cap")

    assert calls == ["qwen3:8b"]

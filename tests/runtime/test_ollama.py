from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import patch
from urllib.request import Request

from ois.runtime.ollama import OllamaProvider


class FakeResponse(BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def test_ollama_provider_implements_generate_contract() -> None:
    captured: list[Request] = []

    def fake_urlopen(request: Request, *, timeout: float) -> FakeResponse:
        captured.append(request)
        return FakeResponse(
            json.dumps(
                {
                    "model": "qwen3:8b",
                    "response": "hello from ollama",
                    "done": True,
                }
            ).encode()
        )

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

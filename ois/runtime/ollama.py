"""Ollama adapter for the canonical OIS LLM gateway."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any


class OllamaProvider:
    """Minimal local provider implementing the OIS LLMProvider contract."""

    provider_id = "ollama"

    def __init__(self, base_url: str | None = None, timeout: float = 120.0) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.timeout = timeout

    def invoke(self, model: str, request: dict[str, Any]) -> Any:
        payload = {
            "model": model,
            "prompt": str(request["prompt"]),
            "stream": False,
        }
        options = request.get("ollama_options")
        if isinstance(options, dict):
            payload["options"] = options

        body = json.dumps(payload).encode("utf-8")
        http_request = Request(
            f"{self.base_url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=self.timeout) as response:
                result = json.load(response)
        except (HTTPError, URLError) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        if not isinstance(result, dict) or not isinstance(result.get("response"), str):
            raise RuntimeError("Ollama returned an invalid generate response")
        return result

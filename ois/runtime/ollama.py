"""Ollama adapter for the canonical OIS LLM gateway."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaProvider:
    """Adapter wrapping local Ollama service calls."""

    provider_id: str = "ollama"

    def __init__(self, base_url: str | None = None, timeout: float = 120.0) -> None:
        default_url = "http://127.0.0.1:11434"
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or default_url).rstrip("/")
        self.timeout = timeout

    def invoke(self, model: str, request: dict[str, Any]) -> Any:
        payload = {
            "model": model,
            "prompt": request.get("prompt", ""),
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

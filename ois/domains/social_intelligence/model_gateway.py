"""Registered external model provider for Social Intelligence prediction."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.request import Request, urlopen

from ois.architecture.fabrics import LLMGatewaySpec, ModelRoute
from ois.runtime.llm_gateway import LLMGateway


@dataclass(frozen=True)
class OpenAIResponsesProvider:
    """OpenAI Responses API provider using an injected environment credential."""

    api_key: str
    provider_id: str = "openai"
    base_url: str = "https://api.openai.com/v1/responses"

    def invoke(self, model: str, request: dict[str, object]) -> object:
        payload = {"model": model, "input": str(request["prompt"])}
        body = json.dumps(payload).encode("utf-8")
        http_request = Request(
            self.base_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(http_request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, Mapping):
            raise RuntimeError("OpenAI Responses API returned a non-object response")
        text = result.get("output_text")
        if isinstance(text, str):
            return text
        raise RuntimeError("OpenAI Responses API response did not contain output_text")


def build_openai_social_gateway(
    *,
    api_key: str | None = None,
    model: str = "gpt-5.6-luna",
) -> LLMGateway:
    """Create and register the production OpenAI route used by M15."""
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required to build the OpenAI social gateway")
    gateway = LLMGateway(
        LLMGatewaySpec(
            ref_id="ois.social.model-gateway",
            version="1.0.0",
            providers=("openai",),
            routing_policy="capability_first",
            retry_policy="bounded",
            fallback_policy="next_compatible",
            structured_output=True,
        )
    )
    gateway.register_provider(OpenAIResponsesProvider(key))
    gateway.register_route(
        ModelRoute(
            ref_id="social-prediction-openai",
            version="1.0.0",
            provider="openai",
            model=model,
            capabilities=("social_prediction",),
        )
    )
    return gateway

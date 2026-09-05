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
        http_request = Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
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


class GatewayBackedM15Prediction:
    """M15 provider that obtains predictions through the registered gateway."""

    def __init__(self, gateway: LLMGateway) -> None:
        from .runtime_capabilities import M15Prediction

        self._gateway = gateway
        self.contract = M15Prediction.contract

    def invoke(self, request: object) -> object:
        from ois.kernel.contracts import InvocationRequest, InvocationResult
        from ois.kernel.types import InvocationStatus

        if not isinstance(request, InvocationRequest):
            raise TypeError("M15 gateway adapter requires InvocationRequest")
        genome = request.input.get("content_genome")
        if not isinstance(genome, Mapping):
            raise TypeError("content_genome must be an object")
        prompt = (
            "Return JSON only with numeric fields: scroll_stop_probability, "
            "retention_probability, completion_probability, rewatch_probability, "
            "share_probability, save_probability, comment_probability, "
            "follow_probability, profile_visit_probability, conversion_probability, confidence. "
            f"Content Genome: {json.dumps(dict(genome), sort_keys=True)}"
        )
        raw = self._gateway.invoke(
            str(request.invocation_id),
            prompt,
            capabilities={"social_prediction"},
        )
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, Mapping):
            raise TypeError("model gateway prediction must be a JSON object")
        prediction = dict(raw)
        prediction["model_version"] = "gateway"
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"prediction": prediction},
            metadata={"model_gateway": "ois.social.model-gateway"},
        )

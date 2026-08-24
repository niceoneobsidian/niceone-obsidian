from dataclasses import dataclass

import pytest

from ois.architecture.fabrics import LLMGatewaySpec, ModelRoute
from ois.runtime.llm_gateway import InferenceRecord, LLMGateway


@dataclass
class Provider:
    provider_id: str
    value: str
    fail: bool = False

    def invoke(self, model: str, request: dict[str, object]) -> object:
        if self.fail:
            raise RuntimeError("provider unavailable")
        return {"model": model, "prompt": request["prompt"], "value": self.value}


def build_gateway() -> LLMGateway:
    gateway = LLMGateway(spec=LLMGatewaySpec(ref_id="gateway"))
    gateway.register_route(
        ModelRoute(
            ref_id="route-a",
            provider="primary",
            model="model-a",
            capabilities=("text",),
            cost_profile={"input": 1.0},
        )
    )
    gateway.register_route(
        ModelRoute(
            ref_id="route-b",
            provider="fallback",
            model="model-b",
            capabilities=("text",),
            cost_profile={"input": 2.0},
        )
    )
    gateway.register_provider(Provider("primary", "primary"))
    gateway.register_provider(Provider("fallback", "fallback"))
    return gateway


def test_gateway_routes_and_records_inference() -> None:
    gateway = build_gateway()

    result = gateway.invoke("request-1", "hello", capabilities={"text"})

    assert result["value"] == "primary"
    assert len(gateway.records) == 1
    assert isinstance(gateway.records[0], InferenceRecord)
    assert gateway.records[0].status == "succeeded"


def test_gateway_falls_back_to_next_compatible_provider() -> None:
    gateway = build_gateway()
    gateway.providers["primary"] = Provider("primary", "primary", fail=True)

    result = gateway.invoke("request-2", "hello", capabilities={"text"})

    assert result["value"] == "fallback"
    assert [record.status for record in gateway.records] == ["failed", "succeeded"]


def test_gateway_rejects_missing_capability_route() -> None:
    gateway = build_gateway()

    with pytest.raises(LookupError):
        gateway.invoke("request-3", "hello", capabilities={"vision"})

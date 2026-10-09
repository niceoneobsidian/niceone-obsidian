from __future__ import annotations

from typing import Any

import pytest

from ois.architecture.fabrics import LLMGatewaySpec, ModelRoute
from ois.runtime.fabrics import FabricRuntime


def _route(
    ref_id: str,
    provider: str,
    model: str,
    cost: float,
) -> ModelRoute:
    return ModelRoute(
        ref_id=ref_id,
        provider=provider,
        model=model,
        capabilities=("text",),
        cost_profile={"local": cost},
    )


def _runtime() -> FabricRuntime:
    runtime = FabricRuntime()
    runtime.configure_gateway(
        LLMGatewaySpec(
            ref_id="fabric-models",
            providers=("primary", "fallback"),
            fallback_policy="next_compatible",
        )
    )
    return runtime


def test_fabric_gateway_uses_canonical_engine_and_records_success() -> None:
    runtime = _runtime()
    runtime.model_router.register(_route("primary-route", "primary", "local-primary", 0.0))
    calls: list[tuple[str, dict[str, Any]]] = []

    def provider(model: str, request: dict[str, Any]) -> dict[str, str]:
        calls.append((model, request))
        return {"response": "fabric inference succeeded"}

    assert runtime.llm_gateway is not None
    runtime.llm_gateway.register_provider("primary", provider)

    result = runtime.llm_gateway.invoke(
        "Explain OIS.",
        capabilities={"text"},
        options={"request_id": "fabric-request-1"},
    )

    assert result == {"response": "fabric inference succeeded"}
    assert calls[0][0] == "local-primary"
    assert calls[0][1]["prompt"] == "Explain OIS."
    assert len(runtime.llm_gateway.engine.records) == 1
    record = runtime.llm_gateway.engine.records[0]
    assert (record.request_id, record.provider, record.model, record.status) == (
        "fabric-request-1",
        "primary",
        "local-primary",
        "succeeded",
    )
    assert runtime.llm_gateway.telemetry[0]["status"] == "succeeded"


def test_fabric_gateway_falls_back_and_records_both_attempts() -> None:
    runtime = _runtime()
    runtime.model_router.register(_route("primary-route", "primary", "local-primary", 0.0))
    runtime.model_router.register(_route("fallback-route", "fallback", "local-fallback", 1.0))
    assert runtime.llm_gateway is not None

    def fail_provider(model: str, request: dict[str, Any]) -> Any:
        raise RuntimeError("simulated provider failure")

    runtime.llm_gateway.register_provider("primary", fail_provider)
    runtime.llm_gateway.register_provider(
        "fallback",
        lambda model, request: {"response": f"served by {model}"},
    )

    result = runtime.llm_gateway.invoke(
        "Run with fallback.",
        capabilities={"text"},
        options={"request_id": "fabric-request-2"},
    )

    assert result == {"response": "served by local-fallback"}
    records = runtime.llm_gateway.engine.records
    assert [(record.model, record.status) for record in records] == [
        ("local-primary", "failed"),
        ("local-fallback", "succeeded"),
    ]
    assert [item["status"] for item in runtime.llm_gateway.telemetry] == [
        "failed",
        "succeeded",
    ]


def test_fabric_gateway_does_not_fallback_when_policy_disallows_it() -> None:
    runtime = FabricRuntime()
    runtime.configure_gateway(
        LLMGatewaySpec(
            ref_id="single-attempt",
            providers=("primary", "fallback"),
            fallback_policy="none",
        )
    )
    runtime.model_router.register(_route("primary-route", "primary", "local-primary", 0.0))
    runtime.model_router.register(_route("fallback-route", "fallback", "local-fallback", 1.0))
    assert runtime.llm_gateway is not None
    runtime.llm_gateway.register_provider(
        "primary",
        lambda model, request: (_ for _ in ()).throw(RuntimeError("primary failed")),
    )
    runtime.llm_gateway.register_provider(
        "fallback",
        lambda model, request: {"response": "must not be called"},
    )

    with pytest.raises(RuntimeError, match="primary failed"):
        runtime.llm_gateway.invoke("No fallback.", capabilities={"text"})

    assert len(runtime.llm_gateway.engine.records) == 1
    assert runtime.llm_gateway.engine.records[0].status == "failed"

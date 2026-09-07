import os

import pytest

from ois.integration.langgraph_runtime import build_ois_graph
from ois.integration.spine import OISSpine, SpineRequest
from ois.kernel import (
    CapabilityContract,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
    RiskLevel,
    SideEffectLevel,
)
from ois.registries import CapabilityRegistry
from ois.runtime.redis_coordination import RedisCoordination


class RuntimeEcho:
    @property
    def contract(self) -> CapabilityContract:
        return CapabilityContract(
            capability_id="test.runtime.echo",
            version="1.0.0",
            description="runtime integration capability",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output=dict(request.input),
        )


def make_spine() -> OISSpine:
    registry = CapabilityRegistry()
    registry.register("test.runtime.echo", "1.0.0", RuntimeEcho())
    return OISSpine(registry)


def test_langgraph_adapter_executes_through_ois_spine() -> None:
    graph = build_ois_graph(make_spine())
    state = graph.invoke(
        {
            "request": SpineRequest(
                objective="LangGraph runtime integration",
                capability_id="test.runtime.echo",
                capability_version="1.0.0",
                input={"ok": True},
            )
        }
    )
    assert state["status"] == "succeeded"
    assert state["output"] == {"ok": True}


@pytest.mark.skipif(
    not os.getenv("OIS_REDIS_URL"),
    reason="OIS_REDIS_URL not configured",
)
def test_redis_coordination_lease() -> None:
    coordination = RedisCoordination(os.environ["OIS_REDIS_URL"])
    assert coordination.ping() is True
    with coordination.lease("p0-test", ttl_seconds=10) as token:
        assert token

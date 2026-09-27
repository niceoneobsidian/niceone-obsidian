"""Contract tests for deterministic routing."""

from __future__ import annotations

import pytest

from ois.registries import AgentRegistry, CapabilityRegistry, ModelRegistry, ToolRegistry
from ois.routing import Router, RouteRequest


def test_resolves_capability_by_exact_identity() -> None:
    registry = CapabilityRegistry()
    value = object()
    registry.register("capability.example", "1.0.0", value)
    router = Router(capabilities=registry)

    result = router.resolve_capability(RouteRequest("capability.example", "1.0.0"))

    assert result.object_id == "capability.example"
    assert result.version == "1.0.0"
    assert result.value is value


def test_resolves_each_registered_object_type() -> None:
    capability = object()
    agent = object()
    model = object()
    tool = object()

    capabilities = CapabilityRegistry()
    agents = AgentRegistry()
    models = ModelRegistry()
    tools = ToolRegistry()
    capabilities.register("capability", "1.0.0", capability)
    agents.register("agent", "1.0.0", agent)
    models.register("model", "1.0.0", model)
    tools.register("tool", "1.0.0", tool)

    router = Router(
        capabilities=capabilities,
        agents=agents,
        models=models,
        tools=tools,
    )

    assert router.resolve_capability(RouteRequest("capability", "1.0.0")).value is capability
    assert router.resolve_agent(RouteRequest("agent", "1.0.0")).value is agent
    assert router.resolve_model(RouteRequest("model", "1.0.0")).value is model
    assert router.resolve_tool(RouteRequest("tool", "1.0.0")).value is tool


def test_version_isolation_is_preserved() -> None:
    registry = CapabilityRegistry()
    v1 = object()
    v2 = object()
    registry.register("capability", "1.0.0", v1)
    registry.register("capability", "2.0.0", v2)
    router = Router(capabilities=registry)

    assert router.resolve_capability(RouteRequest("capability", "1.0.0")).value is v1
    assert router.resolve_capability(RouteRequest("capability", "2.0.0")).value is v2


def test_missing_route_fails_without_fallback_execution() -> None:
    router = Router()

    with pytest.raises(KeyError, match="not registered"):
        router.resolve_capability(RouteRequest("missing", "1.0.0"))


def test_router_returns_reference_without_executing_it() -> None:
    calls: list[object] = []

    def capability(payload: object) -> object:
        calls.append(payload)
        return payload

    registry = CapabilityRegistry()
    registry.register("capability", "1.0.0", capability)
    router = Router(capabilities=registry)

    result = router.resolve_capability(RouteRequest("capability", "1.0.0"))

    assert result.value is capability
    assert calls == []

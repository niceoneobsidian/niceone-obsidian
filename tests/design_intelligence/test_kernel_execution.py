from __future__ import annotations

from typing import Any

from ois.design_intelligence.fabric import DesignCapabilityFabric
from ois.design_intelligence.kernel_integration import register_design_kernel_capabilities
from ois.kernel.checkpoint import InMemoryCheckpointStore
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity


class StubBrandIdentityProvider:
    def execute(self, capability: Any, context: ExecutionContext) -> dict[str, Any]:
        return {
            "artifact_type": "brand_identity_plan",
            "capability": capability.id,
            "objective": context.objective,
            "brief": context.intent,
        }


def build_runtime() -> tuple[ExecutionRuntime, ExecutionContext, EvidenceLedger]:
    registry = CapabilityRegistry()
    fabric = register_design_kernel_capabilities(registry)
    fabric.register_provider("brand.identity", StubBrandIdentityProvider())
    evidence = EvidenceLedger()
    runtime = ExecutionRuntime(registry, InMemoryCheckpointStore(), evidence)
    context = ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id="test-tenant",
            workflow_id="design.brand_identity",
            workflow_version="1.0",
        ),
        objective="Create a governed brand identity plan",
    )
    return runtime, context, evidence


def test_design_capabilities_are_registered_in_canonical_kernel_registry() -> None:
    registry = CapabilityRegistry()
    register_design_kernel_capabilities(registry)

    assert registry.has("brand.identity", "1.0.0")
    assert registry.has("quality.visual_qa", "1.0.0")
    assert len([entry for entry in registry.list() if entry.id.startswith(("brand.", "ui.", "visual.", "production.", "marketing.", "quality."))]) == 17


def test_design_capability_executes_through_ois_kernel() -> None:
    runtime, context, evidence = build_runtime()

    result = runtime.execute(
        context,
        "brand.identity",
        "1.0.0",
        {"brief": "Build a differentiated intelligence-system identity"},
        invocation_id="design-vertical-slice-001",
    )

    assert result.status.value == "succeeded"
    assert result.output["capability"] == "brand.identity"
    assert result.output["output"]["artifact_type"] == "brand_identity_plan"
    assert any(event.event_type == "execution.authorized" for event in evidence.list(context.identity.execution_id))
    assert any(event.event_type == "capability.completed" for event in evidence.list(context.identity.execution_id))


def test_unbound_design_provider_fails_explicitly() -> None:
    registry = CapabilityRegistry()
    register_design_kernel_capabilities(registry)
    runtime = ExecutionRuntime(registry, InMemoryCheckpointStore(), EvidenceLedger())
    context = ExecutionContext(
        identity=ExecutionIdentity(tenant_id="test-tenant", workflow_id="design", workflow_version="1.0"),
        objective="Execute unbound design capability",
    )

    result = runtime.execute(
        context,
        "brand.identity",
        "1.0.0",
        {"brief": "test"},
        invocation_id="design-unbound-001",
    )

    assert result.status.value == "failed"
    assert result.error["type"] == "DesignProviderUnavailable"
    assert result.error["capability_status"] == "unbound"

from __future__ import annotations

from ois.architecture.fabrics import WorkflowSpec
from ois.kernel.checkpoint import InMemoryCheckpointStore
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.runtime.fabrics import FabricRuntime, register_fabric_capabilities


def test_structural_fabric_capability_executes_through_kernel() -> None:
    fabric_runtime = FabricRuntime()
    fabric_runtime.bind_workflow(
        WorkflowSpec(
            "social.workflow",
            nodes=("collect", "analyze"),
            edges=(("collect", "analyze"),),
        )
    )

    registry = CapabilityRegistry()
    register_fabric_capabilities(registry, fabric_runtime)
    evidence = EvidenceLedger()
    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=evidence,
    )
    context = ExecutionContext(
        identity=ExecutionIdentity(
            workflow_id="social.workflow",
            workflow_version="1.0.0",
        ),
        objective="start social workflow",
    )

    result = runtime.execute(
        context,
        "fabric.workflow",
        "1.0.0",
        {
            "workflow_id": "social.workflow",
            "execution_id": str(context.identity.execution_id),
            "inputs": {"topic": "AI"},
        },
        invocation_id="integration-1",
    )

    assert result.status.value == "succeeded"
    assert result.output["workflow_id"] == "social.workflow"
    assert any(
        event.event_type == "execution.authorized"
        for event in evidence.list(context.identity.execution_id)
    )
    assert any(
        event.event_type == "execution.checkpointed"
        for event in evidence.list(context.identity.execution_id)
    )

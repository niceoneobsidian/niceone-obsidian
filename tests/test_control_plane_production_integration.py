from __future__ import annotations

from typing import Any

from control_plane.controller import ControlPlane
from control_plane.lifecycle import OISProductionLifecycle
from control_plane.request import ControlRequest
from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.types import InvocationStatus
from production.workers import LeaseQueue


class EchoCapability:
    contract = CapabilityContract(
        capability_id="test.echo",
        version="1.0.0",
        description="Deterministic integration-test capability",
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"echo": dict(request.input)},
        )


def build_lifecycle() -> OISProductionLifecycle:
    registry = CapabilityRegistry()
    registry.register(EchoCapability())
    return OISProductionLifecycle(ControlPlane(capabilities=registry), registry)


def test_control_plane_executes_through_kernel_and_emits_shared_evidence() -> None:
    lifecycle = build_lifecycle()
    result = lifecycle.execute(
        ControlRequest("test.echo", "1.0.0", {"value": 7}),
        objective="prove integrated execution",
        tenant_id="tenant-1",
        subject_id="operator-1",
        permissions=frozenset({"execution.invoke"}),
        environment="staging",
        attributes={"environment": "staging"},
    )

    assert result.result.status is InvocationStatus.SUCCEEDED
    assert result.result.output == {"echo": {"value": 7}}
    assert result.evidence_event_ids
    assert lifecycle.evidence.verify_chain()
    event_types = [event.event_type for event in lifecycle.evidence.events(result.execution_id)]
    assert "execution.received" in event_types
    assert "execution.authorized" in event_types
    assert "capability.started" in event_types
    assert "capability.completed" in event_types
    assert "execution.checkpointed" in event_types
    assert lifecycle.world.entity(result.semantic_entity_id) is not None
    assert lifecycle.world.facts(result.semantic_entity_id)
    assert result.learning_state == "PENDING_APPROVAL"


def test_worker_enters_control_plane_and_kernel_instead_of_calling_capability_directly() -> None:
    lifecycle = build_lifecycle()
    queue = LeaseQueue()
    work_id = queue.enqueue(
        {
            "capability_id": "test.echo",
            "capability_version": "1.0.0",
            "input": {"worker": True},
            "objective": "prove worker integration",
            "tenant_id": "tenant-1",
            "subject_id": "worker-1",
            "permissions": ["execution.invoke"],
            "environment": "staging",
            "attributes": {"environment": "staging"},
        }
    )

    worker = lifecycle.worker(queue, "worker-1")
    assert worker.run_once()
    item = queue.get(work_id)
    assert item is not None
    assert item.status == "SUCCEEDED"
    assert isinstance(item.result.result, InvocationResult)
    assert item.result.result.status is InvocationStatus.SUCCEEDED
    assert lifecycle.evidence.verify_chain()


def test_kernel_rbac_abac_denies_missing_permission_before_capability_execution() -> None:
    lifecycle = build_lifecycle()
    result = lifecycle.execute(
        ControlRequest("test.echo", "1.0.0", {"value": 1}),
        objective="deny unauthorized execution",
        tenant_id="tenant-1",
        subject_id="viewer",
        permissions=frozenset(),
        environment="staging",
        attributes={"environment": "staging"},
    )

    assert result.result.status is InvocationStatus.FAILED
    assert result.result.error is not None
    assert "permission is missing" in str(result.result.error)
    assert lifecycle.evidence.verify_chain()

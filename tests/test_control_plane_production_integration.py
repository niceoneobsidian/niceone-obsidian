from __future__ import annotations

import pytest

from control_plane.controller import ControlPlane
from control_plane.lifecycle import OISProductionLifecycle
from control_plane.request import ControlRequest
from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.types import InvocationStatus
from production.control_plane import AuthorizationError, Subject
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


class FailingCapability:
    contract = CapabilityContract(
        capability_id="test.fail",
        version="1.0.0",
        description="Deterministic failing capability for rollout recovery",
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.FAILED,
            error={"type": "DeliberateFailure"},
        )


def build_lifecycle() -> OISProductionLifecycle:
    registry = CapabilityRegistry()
    registry.register(EchoCapability())
    registry.register(FailingCapability())
    return OISProductionLifecycle(ControlPlane(capabilities=registry), registry)


def execute(lifecycle: OISProductionLifecycle, capability_id: str):
    return lifecycle.execute(
        ControlRequest(capability_id, "1.0.0", {"value": 7}),
        objective="prove integrated execution",
        tenant_id="tenant-1",
        subject_id="operator-1",
        permissions=frozenset({"execution.invoke"}),
        environment="staging",
        attributes={"environment": "staging"},
    )


def test_control_plane_executes_through_kernel_and_emits_shared_evidence() -> None:
    lifecycle = build_lifecycle()
    result = execute(lifecycle, "test.echo")

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
    with pytest.raises(AuthorizationError, match="permission is missing"):
        lifecycle.execute(
            ControlRequest("test.echo", "1.0.0", {"value": 1}),
            objective="deny unauthorized execution",
            tenant_id="tenant-1",
            subject_id="viewer",
            permissions=frozenset(),
            environment="staging",
            attributes={"environment": "staging"},
        )


def test_canary_decision_uses_actual_kernel_execution_outcomes() -> None:
    lifecycle = build_lifecycle()
    successful = execute(lifecycle, "test.echo")
    failed = execute(lifecycle, "test.fail")
    release_subject = Subject(
        "release-operator",
        "tenant-1",
        frozenset({"release-manager"}),
        {"environment": "staging"},
    )

    rollout = lifecycle.rollout_from_executions(
        candidate="v2",
        environment="staging",
        previous="v1",
        executions=[successful, failed],
        traffic_percent=10,
        latency_ms=100.0,
        release_subject=release_subject,
    )

    assert rollout.state == "ROLLED_BACK"
    assert rollout.decision.success_rate == 0.5
    assert len(rollout.execution_ids) == 2
    assert lifecycle.evidence.verify_chain()
    assert any(
        event.event_type == "rollout.rollback.verified"
        for event in lifecycle.evidence.events()
    )

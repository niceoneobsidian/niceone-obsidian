from __future__ import annotations

from ois.control_plane import ControlPlane, ControlRequest, IntegratedExecution
from ois.kernel import (
    CapabilityContract,
    CapabilityRegistry,
    EvidenceLedger,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    FailureClass,
    InMemoryCheckpointStore,
    InvocationResult,
    InvocationStatus,
)


class FlakyCapability:
    contract = CapabilityContract(
        capability_id="demo.flaky",
        version="1.0.0",
        description="P0 recovery probe",
        input_schema={"type": "object", "required": ["value"]},
        output_schema={"type": "object", "required": ["value"]},
    )

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, request):
        self.calls += 1
        if self.calls == 1:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={
                    "type": "TransientProbeFailure",
                    "message": "deliberate transient failure",
                    "failure_class": FailureClass.TRANSIENT.value,
                },
            )
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"value": request.input["value"]},
        )


def test_p0_integrated_spine_recovers_and_records_evidence() -> None:
    registry = CapabilityRegistry()
    capability = FlakyCapability()
    registry.register(capability)
    evidence = EvidenceLedger()
    checkpoints = InMemoryCheckpointStore()
    runtime = ExecutionRuntime(registry, checkpoints, evidence)
    spine = IntegratedExecution(ControlPlane(capabilities=registry), runtime)

    context = spine.execute(
        objective="prove the integrated P0 execution spine",
        request=ControlRequest(
            capability_id="demo.flaky",
            capability_version="1.0.0",
            input={"value": "recovered"},
        ),
    )

    assert capability.calls == 2
    assert context.status.value == "completed"
    assert context.retry_count == 1
    assert checkpoints.exists(context.identity.execution_id)

    events = evidence.list(context.identity.execution_id)
    event_types = [event.event_type for event in events]
    assert "execution.failure" in event_types
    assert "execution.recovery_decision" in event_types
    assert "execution.checkpointed" in event_types
    assert "execution.completed" in event_types


def test_failed_invocation_is_not_idempotency_cached_before_recovery() -> None:
    registry = CapabilityRegistry()
    capability = FlakyCapability()
    registry.register(capability)
    evidence = EvidenceLedger()
    runtime = ExecutionRuntime(registry, InMemoryCheckpointStore(), evidence)
    context = ExecutionContext(
        identity=ExecutionIdentity(),
        objective="retryability probe",
    )

    first = runtime.execute(
        context,
        "demo.flaky",
        "1.0.0",
        {"value": "ok"},
        invocation_id="stable-invocation",
    )
    second = runtime.execute(
        context,
        "demo.flaky",
        "1.0.0",
        {"value": "ok"},
        invocation_id="stable-invocation",
    )

    assert first.status == InvocationStatus.FAILED
    assert second.status == InvocationStatus.SUCCEEDED
    assert capability.calls == 2

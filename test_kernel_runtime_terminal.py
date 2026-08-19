import pytest

from ois.kernel import (
    CapabilityContract,
    CapabilityRegistry,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    ExecutionStatus,
    InMemoryCheckpointStore,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
    RiskLevel,
    SideEffectLevel,
)
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.runtime import ExecutionAlreadyCompleted


class EchoCapability:
    @property
    def contract(self):
        return CapabilityContract(
            capability_id="test.terminal",
            version="1.0.0",
            description="Terminal-state protection test",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request: InvocationRequest):
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"executed": True},
        )


def make_runtime():
    registry = CapabilityRegistry()
    registry.register(EchoCapability())

    return ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=EvidenceLedger(),
    )


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="default"),
        objective="Terminal-state protection test",
    )


def test_completed_execution_cannot_be_reexecuted():
    runtime = make_runtime()
    context = make_context()

    runtime.execute(
        context=context,
        capability_id="test.terminal",
        version="1.0.0",
        input_data={},
    )

    runtime.complete(context)

    assert context.status == ExecutionStatus.COMPLETED

    with pytest.raises(ExecutionAlreadyCompleted):
        runtime.execute(
            context=context,
            capability_id="test.terminal",
            version="1.0.0",
            input_data={},
        )


def test_stopped_execution_cannot_be_reexecuted():
    runtime = make_runtime()
    context = make_context()

    context.set_status(ExecutionStatus.STOPPED)

    with pytest.raises(ExecutionAlreadyCompleted):
        runtime.execute(
            context=context,
            capability_id="test.terminal",
            version="1.0.0",
            input_data={},
        )

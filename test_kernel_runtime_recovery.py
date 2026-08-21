from ois.kernel import (
    CapabilityContract,
    CapabilityRegistry,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    InMemoryCheckpointStore,
    InvocationRequest,
    RiskLevel,
    SideEffectLevel,
)
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.recovery import RecoveryPolicy
from ois.kernel.types import ExecutionStatus, InvocationStatus


class ExplodingCapability:
    @property
    def contract(self):
        return CapabilityContract(
            capability_id="test.exploding",
            version="1.0.0",
            description="Capability that raises an exception.",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request: InvocationRequest):
        raise RuntimeError("intentional runtime failure")


def make_runtime():
    registry = CapabilityRegistry()
    registry.register(ExplodingCapability())

    checkpoint = InMemoryCheckpointStore()
    evidence = EvidenceLedger()

    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=checkpoint,
        evidence=evidence,
        recovery=RecoveryPolicy(max_retries=2),
    )

    return runtime, checkpoint, evidence


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id="tenant-test",
        ),
        objective="Runtime recovery integration test",
    )


def test_runtime_exception_enters_recovery_and_checkpoints():
    runtime, checkpoint, evidence = make_runtime()
    context = make_context()

    result = runtime.execute(
        context=context,
        capability_id="test.exploding",
        version="1.0.0",
        input_data={},
    )

    assert result.status == InvocationStatus.FAILED

    assert result.error["type"] == "RuntimeError"
    assert result.error["failure_class"] == "tool"
    assert result.error["recovery_action"] == "fallback"

    assert context.last_failure.value == "tool"
    assert context.error["recovery_action"] == "fallback"

    assert context.status == ExecutionStatus.EXECUTING

    restored = checkpoint.load(context.identity.execution_id)

    assert restored.last_failure.value == "tool"
    assert restored.error["failure_class"] == "tool"
    assert restored.error["recovery_action"] == "fallback"


def test_runtime_failure_is_recorded_in_evidence():
    runtime, checkpoint, evidence = make_runtime()
    context = make_context()

    runtime.execute(
        context=context,
        capability_id="test.exploding",
        version="1.0.0",
        input_data={},
    )

    events = evidence.list(context.identity.execution_id)

    failure_events = [event for event in events if event.event_type == "execution.failure"]

    assert len(failure_events) == 1

    event = failure_events[0]

    assert event.data["capability_id"] == "test.exploding"
    assert event.data["failure_class"] == "tool"
    assert event.data["recovery_action"] == "fallback"
    assert "intentional runtime failure" in event.data["error"]


def test_runtime_does_not_retry_automatically():
    runtime, checkpoint, evidence = make_runtime()
    context = make_context()

    result = runtime.execute(
        context=context,
        capability_id="test.exploding",
        version="1.0.0",
        input_data={},
    )

    assert result.status == InvocationStatus.FAILED

    assert context.retry_count == 0

    assert context.recovery_attempts == 0


print("KERNEL RUNTIME RECOVERY TEST: PASS")

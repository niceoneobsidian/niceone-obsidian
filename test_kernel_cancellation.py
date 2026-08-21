from ois.kernel import (
    CancellationToken,
    CapabilityContract,
    CapabilityRegistry,
    ExecutionCancellation,
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


class CancellationAwareCapability:
    def __init__(self):
        self.invocations = 0

    @property
    def contract(self):
        return CapabilityContract(
            capability_id="test.cancellation",
            version="1.0.0",
            description="Cancellation integration capability",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request: InvocationRequest):
        self.invocations += 1

        token = request.cancellation

        if token is not None:
            token.raise_if_cancelled()

        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"executed": True},
        )


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id="tenant-cancellation-test",
        ),
        objective="Cancellation integration test",
    )


def make_runtime(capability, token=None):
    registry = CapabilityRegistry()
    registry.register(capability)

    return ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=EvidenceLedger(),
        cancellation=token,
    )


def test_cancellation_token_starts_active():
    token = CancellationToken()

    assert token.cancelled is False
    assert token.reason is None


def test_cancellation_token_raises_after_cancel():
    token = CancellationToken()
    token.cancel("user requested cancellation")

    assert token.cancelled is True
    assert token.reason == "user requested cancellation"

    try:
        token.raise_if_cancelled()
    except ExecutionCancellation as exc:
        assert "user requested cancellation" in str(exc)
    else:
        raise AssertionError("Expected ExecutionCancellation")


def test_runtime_stops_before_capability_when_cancelled():
    capability = CancellationAwareCapability()
    token = CancellationToken()
    token.cancel("cancel before execution")

    runtime = make_runtime(
        capability,
        token,
    )

    context = make_context()

    result = runtime.execute(
        context=context,
        capability_id="test.cancellation",
        version="1.0.0",
        input_data={},
        invocation_id="cancel-before-001",
    )

    assert result.status == InvocationStatus.FAILED
    assert result.error["failure_class"] == "cancellation"
    assert result.error["recovery_action"] == "stop"

    assert capability.invocations == 0
    assert context.status == ExecutionStatus.STOPPED


def test_runtime_records_cancellation_evidence():
    capability = CancellationAwareCapability()
    token = CancellationToken()
    token.cancel("operator cancellation")

    evidence = EvidenceLedger()

    registry = CapabilityRegistry()
    registry.register(capability)

    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=evidence,
        cancellation=token,
    )

    context = make_context()

    runtime.execute(
        context=context,
        capability_id="test.cancellation",
        version="1.0.0",
        input_data={},
        invocation_id="cancel-evidence-001",
    )

    events = evidence.list(context.identity.execution_id)

    cancellations = [event for event in events if event.event_type == "execution.cancelled"]

    assert len(cancellations) == 1
    assert cancellations[0].data["invocation_id"] == ("cancel-evidence-001")


def test_cancellation_is_checkpointed():
    capability = CancellationAwareCapability()
    token = CancellationToken()
    token.cancel("checkpoint cancellation")

    checkpoint = InMemoryCheckpointStore()

    registry = CapabilityRegistry()
    registry.register(capability)

    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=checkpoint,
        evidence=EvidenceLedger(),
        cancellation=token,
    )

    context = make_context()

    runtime.execute(
        context=context,
        capability_id="test.cancellation",
        version="1.0.0",
        input_data={},
        invocation_id="cancel-checkpoint-001",
    )

    restored = checkpoint.load(context.identity.execution_id)

    assert restored.status == ExecutionStatus.STOPPED


def test_cancellation_token_is_mutable_and_reusable():
    token = CancellationToken()

    assert token.cancelled is False
    assert token.reason is None

    token.cancel("regression")

    assert token.cancelled is True
    assert token.reason == "regression"

    try:
        token.raise_if_cancelled()
    except ExecutionCancellation as exc:
        assert str(exc) == "regression"
    else:
        raise AssertionError("Expected ExecutionCancellation")

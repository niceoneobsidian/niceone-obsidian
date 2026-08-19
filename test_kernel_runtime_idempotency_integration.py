from ois.kernel import (
    CapabilityContract,
    CapabilityRegistry,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    InMemoryCheckpointStore,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
    RiskLevel,
    SideEffectLevel,
)
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.idempotency import (
    InMemoryIdempotencyStore,
)


class CountingCapability:
    def __init__(self):
        self.invocations = 0

    @property
    def contract(self):
        return CapabilityContract(
            capability_id="test.idempotent",
            version="1.0.0",
            description="Idempotency integration test capability",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
        )

    def invoke(self, request: InvocationRequest):
        self.invocations += 1

        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={
                "invocations": self.invocations,
            },
        )


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id="tenant-test",
        ),
        objective="Runtime idempotency integration test",
    )


def make_runtime(capability):
    registry = CapabilityRegistry()
    registry.register(capability)

    return ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=EvidenceLedger(),
        idempotency=InMemoryIdempotencyStore(),
    )


def test_same_invocation_id_does_not_reexecute_capability():
    capability = CountingCapability()
    runtime = make_runtime(capability)
    context = make_context()

    first = runtime.execute(
        context=context,
        capability_id="test.idempotent",
        version="1.0.0",
        input_data={"value": 1},
        invocation_id="inv-fixed-001",
    )

    second = runtime.execute(
        context=context,
        capability_id="test.idempotent",
        version="1.0.0",
        input_data={"value": 1},
        invocation_id="inv-fixed-001",
    )

    assert capability.invocations == 1
    assert first.invocation_id == "inv-fixed-001"
    assert second.invocation_id == "inv-fixed-001"
    assert second.output == first.output


def test_different_invocation_ids_execute_independently():
    capability = CountingCapability()
    runtime = make_runtime(capability)
    context = make_context()

    first = runtime.execute(
        context=context,
        capability_id="test.idempotent",
        version="1.0.0",
        input_data={"value": 1},
        invocation_id="inv-001",
    )

    second = runtime.execute(
        context=context,
        capability_id="test.idempotent",
        version="1.0.0",
        input_data={"value": 1},
        invocation_id="inv-002",
    )

    assert capability.invocations == 2
    assert first.invocation_id == "inv-001"
    assert second.invocation_id == "inv-002"
    assert first.output != second.output


def test_idempotency_hit_is_recorded_in_evidence():
    capability = CountingCapability()
    evidence = EvidenceLedger()

    registry = CapabilityRegistry()
    registry.register(capability)

    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=evidence,
        idempotency=InMemoryIdempotencyStore(),
    )

    context = make_context()

    runtime.execute(
        context=context,
        capability_id="test.idempotent",
        version="1.0.0",
        input_data={},
        invocation_id="inv-evidence",
    )

    runtime.execute(
        context=context,
        capability_id="test.idempotent",
        version="1.0.0",
        input_data={},
        invocation_id="inv-evidence",
    )

    events = evidence.list(
        context.identity.execution_id
    )

    hits = [
        event
        for event in events
        if event.event_type
        == "execution.idempotency_hit"
    ]

    assert len(hits) == 1
    assert hits[0].data["invocation_id"] == "inv-evidence"

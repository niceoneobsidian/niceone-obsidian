from ois.kernel import (
    CapabilityContract,
    CapabilityRegistry,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    InMemoryIdempotencyStore,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
    JsonFileCheckpointStore,
    RiskLevel,
    SideEffectLevel,
)
from ois.kernel.evidence import EvidenceLedger


class DurableRecoveryCapability:
    def __init__(self):
        self.invocations = 0

    @property
    def contract(self):
        return CapabilityContract(
            capability_id="test.durable.recovery",
            version="1.0.0",
            description="Durable checkpoint recovery integration capability",
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
                "recovered": True,
            },
        )


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id="tenant-recovery-test",
        ),
        objective="Durable checkpoint recovery integration",
    )


def make_runtime(capability, checkpoint_path):
    registry = CapabilityRegistry()
    registry.register(capability)

    return ExecutionRuntime(
        registry=registry,
        checkpoint_store=JsonFileCheckpointStore(str(checkpoint_path)),
        evidence=EvidenceLedger(),
        idempotency=InMemoryIdempotencyStore(),
    )


def test_checkpoint_can_be_restored_after_runtime_recreation(tmp_path):
    checkpoint_path = tmp_path / "checkpoints"

    capability = DurableRecoveryCapability()
    context = make_context()

    runtime1 = make_runtime(
        capability,
        checkpoint_path,
    )

    result = runtime1.execute(
        context=context,
        capability_id="test.durable.recovery",
        version="1.0.0",
        input_data={"phase": "initial"},
        invocation_id="durable-recovery-001",
    )

    assert result.status == InvocationStatus.SUCCEEDED

    execution_id = context.identity.execution_id

    runtime2 = make_runtime(
        capability,
        checkpoint_path,
    )

    restored = runtime2.checkpoint_store.load(execution_id)

    assert restored.identity.execution_id == execution_id

    assert restored.identity.tenant_id == "tenant-recovery-test"

    assert restored.objective == ("Durable checkpoint recovery integration")


def test_restored_execution_preserves_working_memory(tmp_path):
    checkpoint_path = tmp_path / "checkpoints"

    capability = DurableRecoveryCapability()
    context = make_context()

    runtime1 = make_runtime(
        capability,
        checkpoint_path,
    )

    result = runtime1.execute(
        context=context,
        capability_id="test.durable.recovery",
        version="1.0.0",
        input_data={"phase": "memory"},
        invocation_id="durable-memory-001",
    )

    assert result.status == InvocationStatus.SUCCEEDED

    execution_id = context.identity.execution_id

    runtime2 = make_runtime(
        capability,
        checkpoint_path,
    )

    restored = runtime2.checkpoint_store.load(execution_id)

    assert restored.working_memory
    assert any(value == result.output for value in restored.working_memory.values())


def test_restored_execution_can_continue_with_idempotency(tmp_path):
    checkpoint_path = tmp_path / "checkpoints"

    capability = DurableRecoveryCapability()
    context = make_context()

    runtime1 = make_runtime(
        capability,
        checkpoint_path,
    )

    runtime1.execute(
        context=context,
        capability_id="test.durable.recovery",
        version="1.0.0",
        input_data={"phase": "resume"},
        invocation_id="durable-resume-001",
    )

    assert capability.invocations == 1

    execution_id = context.identity.execution_id

    runtime2 = make_runtime(
        capability,
        checkpoint_path,
    )

    restored = runtime2.checkpoint_store.load(execution_id)

    second = runtime2.execute(
        context=restored,
        capability_id="test.durable.recovery",
        version="1.0.0",
        input_data={"phase": "resume"},
        invocation_id="durable-resume-001",
    )

    assert second.status == InvocationStatus.SUCCEEDED

    # A newly-created runtime has a newly-created in-memory
    # idempotency store, so this test explicitly verifies the
    # checkpoint restoration boundary rather than falsely claiming
    # idempotency persistence across runtime processes.
    assert capability.invocations == 2


def test_checkpoint_store_survives_process_boundary_simulation(tmp_path):
    checkpoint_path = tmp_path / "persistent-checkpoints"

    capability = DurableRecoveryCapability()
    context = make_context()

    runtime1 = make_runtime(
        capability,
        checkpoint_path,
    )

    runtime1.execute(
        context=context,
        capability_id="test.durable.recovery",
        version="1.0.0",
        input_data={"phase": "process-boundary"},
        invocation_id="durable-process-001",
    )

    execution_id = context.identity.execution_id

    del runtime1

    runtime2 = make_runtime(
        capability,
        checkpoint_path,
    )

    restored = runtime2.checkpoint_store.load(execution_id)

    assert restored.identity.execution_id == execution_id
    assert restored.working_memory

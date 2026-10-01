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


class EchoCapability:
    @property
    def contract(self):  # type: ignore
        return CapabilityContract(
            capability_id="test.echo",
            version="1.0.0",
            description="Returns the supplied message.",
            input_schema={
                "type": "object",
                "required": ["message"],
                "properties": {"message": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "required": ["message"],
                "properties": {"message": {"type": "string"}},
            },
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request: InvocationRequest):  # type: ignore
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"message": request.input["message"]},
        )


registry = CapabilityRegistry()
registry.register(EchoCapability())

checkpoint = InMemoryCheckpointStore()
evidence = EvidenceLedger()

runtime = ExecutionRuntime(
    registry=registry,
    checkpoint_store=checkpoint,
    evidence=evidence,
)

execution = ExecutionContext(
    identity=ExecutionIdentity(tenant_id="default"),
    objective="Test Kernel runtime",
)

result = runtime.execute(
    context=execution,
    capability_id="test.echo",
    version="1.0.0",
    input_data={"message": "OIS Kernel runtime operational"},
)

# Runtime executes one task.
assert result.status == InvocationStatus.SUCCEEDED

# Runtime must NOT complete the entire execution.
assert execution.status.value != "completed"

# The orchestrator owns plan-level completion.
runtime.complete(execution)

assert execution.status.value == "completed"

restored = checkpoint.load(execution.identity.execution_id)

assert restored.status.value == "completed"

events = evidence.list(execution.identity.execution_id)

assert len(events) >= 5

print("KERNEL RUNTIME TEST: PASS")
print(f"events={len(events)}")
print(f"status={execution.status.value}")

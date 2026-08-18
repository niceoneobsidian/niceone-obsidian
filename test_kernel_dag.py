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
    PlanBuilder,
    PlanOrchestrator,
    RiskLevel,
    SideEffectLevel,
)
from ois.kernel.evidence import EvidenceLedger


class EchoCapability:
    @property
    def contract(self):
        return CapabilityContract(
            capability_id="test.echo",
            version="1.0.0",
            description="Echo capability",
            input_schema={
                "type": "object",
                "required": ["message"],
                "properties": {
                    "message": {
                        "type": "string"
                    }
                },
            },
            output_schema={
                "type": "object",
                "required": ["message"],
                "properties": {
                    "message": {
                        "type": "string"
                    }
                },
            },
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request: InvocationRequest):
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={
                "message": request.input["message"]
            },
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

orchestrator = PlanOrchestrator(runtime)

plan = (
    PlanBuilder(
        objective="Test deterministic DAG execution"
    )
    .task(
        task_id="step-1",
        capability_id="test.echo",
        capability_version="1.0.0",
        input_data={
            "message": "first"
        },
    )
    .task(
        task_id="step-2",
        capability_id="test.echo",
        capability_version="1.0.0",
        input_data={
            "message": "second"
        },
        dependencies=("step-1",),
    )
    .task(
        task_id="step-3",
        capability_id="test.echo",
        capability_version="1.0.0",
        input_data={
            "message": "third"
        },
        dependencies=("step-2",),
    )
    .build()
)

context = ExecutionContext(
    identity=ExecutionIdentity(
        tenant_id="default"
    ),
    objective=plan.objective,
)

result = orchestrator.execute(
    plan,
    context,
)

assert result.is_complete()

assert result.tasks["step-1"].status.value == "succeeded"
assert result.tasks["step-2"].status.value == "succeeded"
assert result.tasks["step-3"].status.value == "succeeded"

print("KERNEL DAG TEST: PASS")

for task in result.tasks.values():
    print(
        f"{task.task_id}: "
        f"{task.status.value}"
    )

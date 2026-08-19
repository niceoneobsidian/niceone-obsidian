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


class RecordingCapability:
    def __init__(self, capability_id, should_fail=False):
        self.capability_id = capability_id
        self.should_fail = should_fail
        self.invocations = 0

    @property
    def contract(self):
        return CapabilityContract(
            capability_id=self.capability_id,
            version="1.0.0",
            description="Orchestrator integration test capability",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request: InvocationRequest):
        self.invocations += 1

        if self.should_fail:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=request.capability_id,
                status=InvocationStatus.FAILED,
                error={
                    "type": "TestFailure",
                    "message": "Intentional test failure",
                },
            )

        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"executed": True},
        )


def make_runtime(*capabilities):
    registry = CapabilityRegistry()

    for capability in capabilities:
        registry.register(capability)

    return ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=EvidenceLedger(),
    )


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id="tenant-test",
        ),
        objective="Orchestrator failure boundary test",
    )


def test_orchestrator_does_not_complete_failed_plan():
    first = RecordingCapability("test.first")
    second = RecordingCapability(
        "test.second",
        should_fail=True,
    )

    runtime = make_runtime(first, second)
    orchestrator = PlanOrchestrator(runtime)

    plan = (
        PlanBuilder(
            objective="Verify orchestrator failure boundary"
        )
        .task(
            task_id="step-1",
            capability_id="test.first",
            capability_version="1.0.0",
        )
        .task(
            task_id="step-2",
            capability_id="test.second",
            capability_version="1.0.0",
            dependencies=("step-1",),
        )
        .build()
    )

    context = make_context()

    result = orchestrator.execute(
        plan,
        context,
    )

    assert result.is_complete() is False
    assert result.has_failed() is True

    assert result.tasks["step-1"].status.value == "succeeded"
    assert result.tasks["step-2"].status.value == "failed"

    assert first.invocations == 1
    assert second.invocations == 1

    assert context.status.value != "completed"

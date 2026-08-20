from ois.kernel import (
    AgentRegistry,
    CapabilityContract,
    CapabilityRegistry,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    InMemoryCheckpointStore,
    InvocationRequest,
    InvocationStatus,
    PlanBuilder,
    PlanOrchestrator,
    RiskLevel,
    SideEffectLevel,
    Supervisor,
)
from ois.kernel.evidence import EvidenceLedger


class FailingCapability:
    def __init__(self):
        self.invocations = 0

    @property
    def contract(self):
        return CapabilityContract(
            capability_id="test.recovery.failure",
            version="1.0.0",
            description="Capability used to verify recovery orchestration.",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request: InvocationRequest):
        self.invocations += 1
        raise RuntimeError("intentional recovery failure")


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="tenant-test"),
        objective="Recovery orchestration boundary test",
    )


def make_system():
    capability = FailingCapability()

    registry = CapabilityRegistry()
    registry.register(capability)

    checkpoint = InMemoryCheckpointStore()
    evidence = EvidenceLedger()

    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=checkpoint,
        evidence=evidence,
    )

    orchestrator = PlanOrchestrator(runtime)

    supervisor = Supervisor(
        agent_registry=AgentRegistry(),
        orchestrator=orchestrator,
    )

    return capability, checkpoint, evidence, supervisor


def make_plan():
    return (
        PlanBuilder(
            objective="Verify recovery orchestration boundary"
        )
        .task(
            task_id="failing-step",
            capability_id="test.recovery.failure",
            capability_version="1.0.0",
        )
        .build()
    )


def test_recovery_failure_remains_visible_to_supervisor():
    capability, checkpoint, evidence, supervisor = make_system()

    context = make_context()
    plan = make_plan()

    result = supervisor.execute(
        plan,
        context,
    )

    assert result.is_complete() is False
    assert result.has_failed() is True

    assert capability.invocations == 1

    assert context.last_failure is not None
    assert context.error is not None

    decision = supervisor.inspect(context)

    assert decision.action == "fallback"

    restored = checkpoint.load(
        context.identity.execution_id
    )

    assert restored.last_failure is not None

    events = evidence.list(
        context.identity.execution_id
    )

    assert any(
        event.event_type == "execution.failure"
        for event in events
    )

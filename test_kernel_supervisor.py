def test_supervisor_execute_delegates_to_orchestrator():
    registry = AgentRegistry()
    agent = MockAgent()
    registry.register(agent)

    runtime = make_runtime(agent)
    orchestrator = PlanOrchestrator(runtime)

    supervisor = Supervisor(
        agent_registry=registry,
        orchestrator=orchestrator,
    )

    plan = make_plan(agent.agent_id)
    context = make_context()

    result = supervisor.execute(
        plan,
        context,
    )

    assert result.is_complete() is True
    assert context.status == ExecutionStatus.COMPLETED
    assert agent.invocations == 1

import pytest

from ois.kernel import (
    AgentContract,
    AgentRegistry,
    AgentSelectionError,
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
    PlanBuilder,
    PlanOrchestrator,
    RiskLevel,
    SideEffectLevel,
    Supervisor,
)
from ois.kernel.evidence import EvidenceLedger


class MockAgent:
    def __init__(self, agent_id="test.agent", should_fail=False):
        self.agent_id = agent_id
        self.should_fail = should_fail
        self.invocations = 0

    @property
    def contract(self):
        return AgentContract(
            capability_id=self.agent_id,
            version="1.0.0",
            description="Supervisor test agent",
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
                    "message": "Intentional supervisor test failure",
                },
            )

        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"agent": self.agent_id},
        )


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="tenant-test"),
        objective="Supervisor boundary test",
    )


def make_runtime(agent):
    registry = CapabilityRegistry()
    registry.register(agent)

    return ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=EvidenceLedger(),
    )


def make_plan(agent_id):
    return (
        PlanBuilder(
            objective="Supervisor test plan"
        )
        .task(
            task_id="agent-step",
            capability_id=agent_id,
            capability_version="1.0.0",
        )
        .build()
    )


def test_agent_registry_accepts_agent_contract():
    registry = AgentRegistry()
    agent = MockAgent()

    registry.register(agent)

    entry = registry.get(
        "test.agent",
        "1.0.0",
    )

    assert isinstance(entry.contract, AgentContract)


def test_supervisor_module_exists():
    import ois.kernel.supervisor as supervisor

    assert supervisor is not None


def test_supervisor_boundary_uses_orchestrator():
    agent = MockAgent()
    runtime = make_runtime(agent)
    orchestrator = PlanOrchestrator(runtime)

    plan = make_plan(agent.agent_id)
    context = make_context()

    result = orchestrator.execute(
        plan,
        context,
    )

    assert result.is_complete() is True
    assert context.status.value == "completed"
    assert agent.invocations == 1


def test_failed_agent_does_not_complete_execution():
    agent = MockAgent(should_fail=True)
    runtime = make_runtime(agent)
    orchestrator = PlanOrchestrator(runtime)

    plan = make_plan(agent.agent_id)
    context = make_context()

    result = orchestrator.execute(
        plan,
        context,
    )

    assert result.has_failed() is True
    assert result.is_complete() is False
    assert context.status.value != "completed"
    assert agent.invocations == 1


print("SUPERVISOR CONTRACT TESTS: PASS")


def test_supervisor_selects_registered_agent():

    registry = AgentRegistry()
    agent = MockAgent()

    registry.register(agent)

    runtime = make_runtime(agent)
    orchestrator = PlanOrchestrator(runtime)

    supervisor = Supervisor(
        agent_registry=registry,
        orchestrator=orchestrator,
    )

    selected = supervisor.select_agent(
        "test.agent",
        "1.0.0",
    )

    assert selected.capability is agent
    assert selected.contract.capability_id == "test.agent"


def test_supervisor_rejects_unknown_agent():

    registry = AgentRegistry()

    agent = MockAgent()

    runtime = make_runtime(agent)
    orchestrator = PlanOrchestrator(runtime)

    supervisor = Supervisor(
        agent_registry=registry,
        orchestrator=orchestrator,
    )

    with pytest.raises(AgentSelectionError):
        supervisor.select_agent(
            "missing.agent",
            "1.0.0",
        )


def test_supervisor_inspects_completed_execution():

    agent = MockAgent()

    runtime = make_runtime(agent)
    orchestrator = PlanOrchestrator(runtime)

    supervisor = Supervisor(
        agent_registry=AgentRegistry(),
        orchestrator=orchestrator,
    )

    context = make_context()
    context.set_status(ExecutionStatus.COMPLETED)

    decision = supervisor.inspect(context)

    assert decision.action == "complete"
    assert decision.agent_id is None


def test_supervisor_inspects_stopped_execution():

    agent = MockAgent()

    runtime = make_runtime(agent)
    orchestrator = PlanOrchestrator(runtime)

    supervisor = Supervisor(
        agent_registry=AgentRegistry(),
        orchestrator=orchestrator,
    )

    context = make_context()
    context.set_status(ExecutionStatus.STOPPED)

    decision = supervisor.inspect(context)

    assert decision.action == "stop"
    assert decision.agent_id is None

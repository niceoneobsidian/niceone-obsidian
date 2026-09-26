import pytest

from ois.kernel import (
    AgentContract,
    AgentRegistry,
    AgentRoutingError,
    AgentSelectionError,
    AmbiguousAgentError,
    DefaultPolicyEngine,
    EvidenceLedger,
    ExecutionContext,
    ExecutionIdentity,
    InvocationRequest,
    RiskLevel,
    SideEffectLevel,
    Supervisor,
)


class RoutingAgent:
    def __init__(self, name: str, *, permissions=(), risk=RiskLevel.LOW):  # type: ignore
        self.name = name
        self._contract = AgentContract(
            capability_id="test.routing",
            version="1.0.0",
            description=f"Routing agent {name}",
            permissions=permissions,
            risk_level=risk,
            side_effects=SideEffectLevel.NONE,
        )

    @property
    def contract(self):  # type: ignore
        return self._contract

    def invoke(self, request):  # type: ignore
        raise AssertionError("routing tests must not invoke an agent")


def make_context():  # type: ignore
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="tenant-routing"),
        objective="route an agent",
    )


def make_request(context=None):  # type: ignore
    return InvocationRequest(
        invocation_id="routing-001",
        capability_id="test.routing",
        input={},
        execution=context or make_context(),
    )


def test_agent_registry_routes_authorized_agent_deterministically():  # type: ignore
    registry = AgentRegistry()
    agent = RoutingAgent("primary")
    registry.register(agent)

    decision = registry.route(
        "test.routing",
        "1.0.0",
        request=make_request(),
        policy=DefaultPolicyEngine(),
    )

    assert decision.selected.capability is agent
    assert decision.reason.startswith("Selected the sole eligible agent")


def test_agent_registry_rejects_unauthorized_agent():  # type: ignore
    registry = AgentRegistry()
    agent = RoutingAgent("restricted", permissions=("agent.execute",))
    registry.register(agent)

    with pytest.raises(AgentRoutingError, match="Missing permissions"):
        registry.route(
            "test.routing",
            "1.0.0",
            request=make_request(),
            policy=DefaultPolicyEngine(),
        )


def test_agent_registry_rejects_unavailable_agent():  # type: ignore
    registry = AgentRegistry()
    registry.register(RoutingAgent("offline"))

    with pytest.raises(AgentRoutingError, match="Agent unavailable"):
        registry.route(
            "test.routing",
            "1.0.0",
            request=make_request(),
            policy=DefaultPolicyEngine(),
            availability=lambda entry: False,
        )


def test_agent_registry_rejects_ambiguous_eligible_candidates():  # type: ignore
    class AmbiguousRegistry(AgentRegistry):
        def list(self):  # type: ignore
            entry = super().list()[0]
            return (entry, entry)

    registry = AmbiguousRegistry()
    registry.register(RoutingAgent("duplicate-view"))

    with pytest.raises(AmbiguousAgentError, match="2 eligible agents"):
        registry.route(
            "test.routing",
            "1.0.0",
            request=make_request(),
            policy=DefaultPolicyEngine(),
        )


def test_supervisor_uses_governed_registry_routing_and_records_selection():  # type: ignore
    registry = AgentRegistry()
    agent = RoutingAgent("primary")
    registry.register(agent)
    evidence = EvidenceLedger()
    supervisor = Supervisor(
        agent_registry=registry,
        evidence=evidence,
    )
    context = make_context()

    selected = supervisor.select_agent(
        "test.routing",
        "1.0.0",
        context=context,
        invocation_id="selection-001",
    )

    assert selected.capability is agent
    events = evidence.list(context.identity.execution_id)
    assert events[-1].event_type == "agent.selection.selected"


def test_supervisor_converts_routing_rejection_to_selection_error_and_evidence():  # type: ignore
    registry = AgentRegistry()
    registry.register(RoutingAgent("restricted", permissions=("agent.execute",)))
    evidence = EvidenceLedger()
    supervisor = Supervisor(
        agent_registry=registry,
        evidence=evidence,
    )
    context = make_context()

    with pytest.raises(AgentSelectionError, match="Missing permissions"):
        supervisor.select_agent(
            "test.routing",
            "1.0.0",
            context=context,
            invocation_id="selection-002",
        )

    events = evidence.list(context.identity.execution_id)
    assert events[-1].event_type == "agent.selection.rejected"


def test_agent_registry_requires_registered_exact_version():  # type: ignore
    registry = AgentRegistry()

    with pytest.raises(AgentRoutingError, match="No agent registered"):
        registry.route(
            "test.routing",
            "9.9.9",
            request=make_request(),
            policy=DefaultPolicyEngine(),
        )

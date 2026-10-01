import pytest

from ois.kernel import (
    AgentContract,
    AgentRegistry,
    AgentSelectionError,
    RiskLevel,
    SideEffectLevel,
    Supervisor,
)


class TestAgent:
    @property
    def contract(self):  # type: ignore
        return AgentContract(
            capability_id="agent.test",
            version="1.0.0",
            description="Test agent for Supervisor selection.",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request):  # type: ignore
        raise NotImplementedError


def test_supervisor_selects_registered_agent():  # type: ignore
    registry = AgentRegistry()
    agent = TestAgent()
    registry.register(agent)

    supervisor = Supervisor(agent_registry=registry)

    entry = supervisor.select_agent("agent.test", "1.0.0")

    assert entry.capability is agent
    assert entry.contract.capability_id == "agent.test"
    assert entry.contract.version == "1.0.0"


def test_supervisor_rejects_unknown_agent():  # type: ignore
    supervisor = Supervisor(agent_registry=AgentRegistry())

    with pytest.raises(AgentSelectionError, match="No agent registered"):
        supervisor.select_agent("agent.missing", "1.0.0")


def test_supervisor_requires_agent_registry_for_selection():  # type: ignore
    supervisor = Supervisor()

    with pytest.raises(AgentSelectionError, match="agent_registry is required"):
        supervisor.select_agent("agent.test", "1.0.0")

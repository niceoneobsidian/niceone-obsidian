from ois.domains.social_growth.integration import register_social_domain
from ois.registries.agent_registry import AgentRegistry
from ois.registries.capability_registry import CapabilityRegistry
from ois.registries.workflow_registry import WorkflowRegistry


def test_social_domain_registers_into_existing_ois_registries():
    capabilities = CapabilityRegistry()
    agents = AgentRegistry()
    workflows = WorkflowRegistry()

    result = register_social_domain(capabilities, agents, workflows)

    assert result.capabilities >= 10
    assert result.agents >= 5
    assert result.workflows == 2
    assert capabilities.contains("social.publish", "1.0.0")
    assert agents.contains("social.supervisor", "1.0.0")
    assert workflows.contains("social.research", "1")
    assert workflows.contains("social.content_publish", "1")

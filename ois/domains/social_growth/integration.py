"""Bridge M13 domain manifests into existing OIS registries.

This is deliberately a thin integration layer: the OIS registries own
identity/versioning while the social domain owns domain metadata and algorithms.
"""

from __future__ import annotations

from dataclasses import dataclass

from ois.registries.agent_registry import AgentRegistry
from ois.registries.capability_registry import CapabilityRegistry
from ois.registries.workflow_registry import WorkflowRegistry

from .patterns import SOCIAL_CAPABILITIES
from .registry import SOCIAL_AGENTS
from .workflows import CONTENT_PUBLISH_WORKFLOW, RESEARCH_WORKFLOW


@dataclass(frozen=True)
class SocialIntegrationResult:
    capabilities: int
    agents: int
    workflows: int


def register_social_domain(
    capabilities: CapabilityRegistry,
    agents: AgentRegistry,
    workflows: WorkflowRegistry,
) -> SocialIntegrationResult:
    """Register M13 descriptors without executing any side effects."""
    for spec in SOCIAL_CAPABILITIES:
        capabilities.register(
            spec.capability_id,
            "1.0.0",
            spec,
            metadata={
                "domain": "social_growth",
                "side_effect": spec.side_effect,
                "requires_approval": spec.requires_approval,
            },
        )
    for agent_spec in SOCIAL_AGENTS:
        agents.register(
            agent_spec.agent_id,
            "1.0.0",
            agent_spec,
            metadata={"domain": "social_growth"},
        )
    for workflow in (RESEARCH_WORKFLOW, CONTENT_PUBLISH_WORKFLOW):
        workflows.register(
            workflow.workflow_id,
            str(workflow.version),
            workflow,
            metadata={"domain": "social_growth"},
        )
    return SocialIntegrationResult(
        capabilities=len(SOCIAL_CAPABILITIES),
        agents=len(SOCIAL_AGENTS),
        workflows=2,
    )

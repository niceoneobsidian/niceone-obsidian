"""Domain manifests for registration with the existing OIS registries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .patterns import SOCIAL_CAPABILITIES


@dataclass(frozen=True)
class SocialAgentSpec:
    agent_id: str
    role: str
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class SocialWorkflowSpec:
    workflow_id: str
    version: int


SOCIAL_AGENTS: tuple[SocialAgentSpec, ...] = (
    SocialAgentSpec("social.research_agent", "Social research and evidence synthesis", ("social.ingest", "social.signal_analysis", "social.research_brief")),
    SocialAgentSpec("social.trend_agent", "Trend and velocity intelligence", ("social.signal_analysis",)),
    SocialAgentSpec("social.audience_agent", "Audience intelligence", ("social.signal_analysis",)),
    SocialAgentSpec("social.competitor_agent", "Competitor intelligence", ("social.signal_analysis",)),
    SocialAgentSpec("social.creative_agent", "Creative intelligence and pattern extraction", ("social.content.generate", "social.learning.update")),
    SocialAgentSpec("social.publisher_agent", "Governed publishing execution", ("social.publish.approve", "social.publish")),
    SocialAgentSpec("social.analytics_agent", "Performance and attribution analysis", ("social.analytics.collect", "social.learning.update")),
    SocialAgentSpec("social.supervisor", "Supervise social domain workflows", tuple(c.capability_id for c in SOCIAL_CAPABILITIES)),
)


def manifest() -> dict[str, list[dict[str, Any]]]:
    return {
        "capabilities": [c.__dict__.copy() for c in SOCIAL_CAPABILITIES],
        "agents": [a.__dict__.copy() for a in SOCIAL_AGENTS],
        "workflows": [
            {"workflow_id": "social.research", "version": 1},
            {"workflow_id": "social.content_publish", "version": 1},
        ],
        "connector_contract": "SocialConnector",
    }

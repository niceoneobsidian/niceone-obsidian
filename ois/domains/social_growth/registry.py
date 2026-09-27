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
    SocialAgentSpec(
        "social.research_agent",
        "Social research and evidence synthesis",
        (
            "social.ingest",
            "social.data_quality",
            "social.entity_resolution",
            "social.topic_clustering",
            "social.trend_detection",
            "social.research_brief",
        ),
    ),
    SocialAgentSpec(
        "social.trend_agent",
        "Trend and velocity intelligence",
        ("social.topic_clustering", "social.trend_detection"),
    ),
    SocialAgentSpec(
        "social.audience_agent", "Audience intelligence", ("social.audience_intelligence",)
    ),
    SocialAgentSpec(
        "social.competitor_agent",
        "Competitor intelligence",
        ("social.entity_resolution", "social.competitor_intelligence"),
    ),
    SocialAgentSpec(
        "social.creative_agent",
        "Creative intelligence and pattern extraction",
        ("social.creative_intelligence", "social.learning.update"),
    ),
    SocialAgentSpec(
        "social.publisher_agent",
        "Governed publishing execution",
        ("social.publish.approve", "social.publish"),
    ),
    SocialAgentSpec(
        "social.analytics_agent",
        "Performance and attribution analysis",
        ("social.analytics.collect", "social.learning.update"),
    ),
    SocialAgentSpec(
        "social.supervisor",
        "Supervise social domain workflows",
        tuple(c.capability_id for c in SOCIAL_CAPABILITIES),
    ),
)


def manifest() -> dict[str, Any]:
    return {
        "capabilities": sorted(
            [c.__dict__.copy() for c in SOCIAL_CAPABILITIES],
            key=lambda c: c["id"] if "id" in c else c.get("name", str(c)),
        ),
        "agents": sorted(
            [a.__dict__.copy() for a in SOCIAL_AGENTS],
            key=lambda a: a["id"] if "id" in a else a.get("name", str(a)),
        ),
        "workflows": [
            {"workflow_id": "social.research", "version": 1},
            {"workflow_id": "social.content_publish", "version": 1},
        ],
        "connector_contract": "SocialConnector",
    }

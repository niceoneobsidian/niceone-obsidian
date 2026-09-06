"""Reusable implementation patterns extracted into OIS-native domain components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .schemas import CreativePattern, Evidence


class MemorySink(Protocol):
    """Kernel-owned memory contract implemented outside the domain."""

    def append(self, namespace: str, record: dict[str, Any]) -> None: ...


@dataclass
class ViralPatternLearner:
    """Convert measured creative observations into versioned memory records."""

    memory: MemorySink
    namespace: str = "social.viral_patterns"

    def learn(self, pattern: CreativePattern) -> None:
        self.memory.append(self.namespace, pattern.model_dump(mode="json"))

    def learn_from_performance(
        self,
        pattern_id: str,
        pattern_type: str,
        pattern_text: str,
        performance_score: float,
        evidence: list[Evidence] | None = None,
        platform: str | None = None,
        audience: str | None = None,
    ) -> CreativePattern:
        confidence = min(1.0, max(0.0, 0.5 + performance_score / 2))
        result = CreativePattern(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            pattern=pattern_text,
            performance_score=performance_score,
            confidence=confidence,
            evidence=evidence or [],
            platform=platform,
            audience=audience,
        )
        self.learn(result)
        return result


@dataclass(frozen=True)
class DomainCapability:
    capability_id: str
    description: str
    input_contract: str
    output_contract: str
    side_effect: bool = False
    requires_approval: bool = False


SOCIAL_CAPABILITIES: tuple[DomainCapability, ...] = (
    DomainCapability("social.ingest", "Ingest social events", "ResearchQuery", "SocialEventBatch"),
    DomainCapability("social.normalize", "Normalize platform events", "SocialEventBatch", "SocialEventBatch"),
    DomainCapability(
        "social.data_quality",
        "Validate canonical social events",
        "SocialEventBatch",
        "DataQualityReport",
    ),
    DomainCapability("social.entity_resolution", "Resolve normalized entities", "SocialEventBatch", "EntityMap"),
    DomainCapability(
        "social.topic_clustering",
        "Cluster dominant social topics",
        "SocialEventBatch",
        "TopicClusters",
    ),
    DomainCapability(
        "social.trend_detection",
        "Detect rising social topics",
        "SocialEventBatch",
        "TrendSignalBatch",
    ),
    DomainCapability(
        "social.audience_intelligence",
        "Build deterministic audience profiles",
        "SocialEventBatch",
        "AudienceProfileBatch",
    ),
    DomainCapability(
        "social.competitor_intelligence",
        "Build competitor/entity profiles",
        "SocialEventBatch",
        "CompetitorProfileBatch",
    ),
    DomainCapability(
        "social.creative_intelligence",
        "Extract creative patterns",
        "SocialEventBatch",
        "CreativePatternBatch",
    ),
    DomainCapability(
        "social.signal_analysis",
        "Derive deterministic social signals",
        "SocialEventBatch",
        "SocialSignalBatch",
    ),
    DomainCapability(
        "social.research_brief",
        "Synthesize evidence-backed findings",
        "SocialSignalBatch",
        "SocialResearchBrief",
    ),
    DomainCapability("social.content.generate", "Generate a content draft", "ContentBrief", "ContentDraft"),
    DomainCapability("social.content.validate", "Validate content", "ContentDraft", "ValidationReport"),
    DomainCapability(
        "social.publish.approve",
        "Request/resolve publishing approval",
        "PublishIntent",
        "ApprovalDecision",
        requires_approval=True,
    ),
    DomainCapability(
        "social.publish",
        "Publish through a registered connector",
        "PublishIntent",
        "ExternalActionResult",
        side_effect=True,
        requires_approval=True,
    ),
    DomainCapability(
        "social.analytics.collect",
        "Collect platform performance",
        "PublicationRef",
        "PerformanceSnapshot",
    ),
    DomainCapability(
        "social.learning.update",
        "Update social learning memory",
        "PerformanceSnapshot",
        "LearningUpdate",
    ),
)


def capability_manifest() -> list[dict[str, Any]]:
    return [c.__dict__.copy() for c in SOCIAL_CAPABILITIES]

"""Pure domain workflow definitions.

A workflow produces typed intents/steps for the OIS orchestrator. It does not
bypass policy or execute external side effects itself.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from .algorithms import signals_from_events
from .intelligence import (
    build_audience_profiles,
    build_competitor_profiles,
    cluster_topics,
    detect_trends,
    validate_events,
)
from .schemas import ExperimentSpec, PublishIntent, SocialEvent, SocialResearchBrief


@dataclass(frozen=True)
class WorkflowStep:
    name: str
    capability_id: str
    input_contract: str
    output_contract: str
    requires_approval: bool = False


@dataclass(frozen=True)
class SocialWorkflow:
    workflow_id: str
    version: int
    steps: tuple[WorkflowStep, ...]


RESEARCH_WORKFLOW = SocialWorkflow(
    workflow_id="social.research",
    version=1,
    steps=(
        WorkflowStep("ingest", "social.ingest", "ResearchQuery", "SocialEventBatch"),
        WorkflowStep("normalize", "social.normalize", "SocialEventBatch", "SocialEventBatch"),
        WorkflowStep("quality", "social.data_quality", "SocialEventBatch", "DataQualityReport"),
        WorkflowStep("entities", "social.entity_resolution", "SocialEventBatch", "EntityMap"),
        WorkflowStep("topics", "social.topic_clustering", "SocialEventBatch", "TopicClusters"),
        WorkflowStep("trends", "social.trend_detection", "SocialEventBatch", "TrendSignalBatch"),
        WorkflowStep("audience", "social.audience_intelligence", "SocialEventBatch", "AudienceProfileBatch"),
        WorkflowStep(
            "competitors",
            "social.competitor_intelligence",
            "SocialEventBatch",
            "CompetitorProfileBatch",
        ),
        WorkflowStep("creative", "social.creative_intelligence", "SocialEventBatch", "CreativePatternBatch"),
        WorkflowStep("analyze", "social.signal_analysis", "SocialEventBatch", "SocialSignalBatch"),
        WorkflowStep("synthesize", "social.research_brief", "SocialSignalBatch", "SocialResearchBrief"),
    ),
)

CONTENT_PUBLISH_WORKFLOW = SocialWorkflow(
    workflow_id="social.content_publish",
    version=1,
    steps=(
        WorkflowStep("generate", "social.content.generate", "ContentBrief", "ContentDraft"),
        WorkflowStep("validate", "social.content.validate", "ContentDraft", "ValidationReport"),
        WorkflowStep("approve", "social.publish.approve", "PublishIntent", "ApprovalDecision", True),
        WorkflowStep("publish", "social.publish", "PublishIntent", "ExternalActionResult", True),
        WorkflowStep("measure", "social.analytics.collect", "PublicationRef", "PerformanceSnapshot"),
        WorkflowStep("learn", "social.learning.update", "PerformanceSnapshot", "LearningUpdate"),
    ),
)


@dataclass
class DomainWorkflowRunner:
    """A testable domain runner; production routing/execution belongs to OIS."""

    handlers: dict[str, Callable[[Any], Any]] = field(default_factory=dict)

    def execute_local(self, workflow: SocialWorkflow, initial: Any) -> Any:
        value = initial
        for step in workflow.steps:
            handler = self.handlers.get(step.capability_id)
            if handler is None:
                raise RuntimeError(f"missing local handler: {step.capability_id}")
            value = handler(value)
        return value


def build_research_brief(query: str, events: Iterable[SocialEvent]) -> SocialResearchBrief:
    materialized = list(events)
    signals = signals_from_events(materialized)
    trend_signals = detect_trends(materialized)
    findings: list[str] = []
    topics = cluster_topics(materialized, top_k=5)
    if topics:
        findings.append("Top topics: " + ", ".join(topic for topic, _, _ in topics))
    if trend_signals:
        findings.append("Emerging trends: " + ", ".join(s.value for s in trend_signals[:5]))
    audience = build_audience_profiles(materialized)
    if audience:
        findings.append("Audience platforms: " + ", ".join(p.platforms[0] for p in audience if p.platforms))
    competitors = build_competitor_profiles(materialized)
    if competitors:
        findings.append("Observed entities: " + ", ".join(c.name for c in competitors[:5]))
    quality = validate_events(materialized)
    confidence = min(1.0, sum(s.confidence for s in signals) / len(signals)) if signals else 0.0
    if quality.rejected:
        confidence *= quality.accepted / max(quality.accepted + quality.rejected, 1)
    return SocialResearchBrief(
        query=query,
        sources=[evidence for event in materialized for evidence in event.evidence],
        signals=signals + trend_signals,
        entities=sorted({entity for event in materialized for entity in event.entities}),
        findings=findings,
        confidence=confidence,
    )


def build_experiment(
    experiment_id: str,
    hypothesis: str,
    metric: str,
    control: dict[str, Any],
    variants: list[dict[str, Any]],
) -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        metric=metric,
        control=control,
        variants=variants,
    )


def publish_intent(platform: str, account_ref: str, content: dict[str, Any]) -> PublishIntent:
    return PublishIntent(platform=platform, account_ref=account_ref, content=content)

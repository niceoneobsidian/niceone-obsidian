"""Pure domain workflow definitions.

A workflow produces typed intents/steps for the OIS orchestrator. It does not
bypass policy or execute external side effects itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .algorithms import signals_from_events
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
    return SocialResearchBrief(
        query=query,
        sources=[evidence for event in materialized for evidence in event.evidence],
        signals=signals,
        entities=sorted({entity for event in materialized for entity in event.entities}),
        findings=[f"Top topic: {signals[0].value}"] if signals else [],
        confidence=min(1.0, sum(s.confidence for s in signals) / len(signals)) if signals else 0.0,
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

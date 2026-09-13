"""Orchestrate the ChatGPT -> genome -> experiment -> outcome -> learning path.

This module is deliberately side-effect-light: ingestion/storage and execution
are injected, while intelligence, comparison, attribution and learning proposal
generation remain deterministic. No proposal is automatically promoted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from ois.domains.social_intelligence.intelligence import ContentGenome, ModalityObservation, build_content_genome

from .analytics_store import MetricObservation
from .attribution import AttributionResult, AttributionTouchpoint, linear_attribution
from .chat_ingestion import ChatObservation, ingest_chat_observations
from .experimentation import ExperimentObservation, ExperimentResult, ExperimentSpec, evaluate_experiment
from .learning import LearningObservation, LearningProposal, propose_learning
from .persistence import SocialEventStore


@dataclass(frozen=True)
class OutcomeObservation:
    outcome_id: str
    entity_id: str
    metric: str
    value: float
    occurred_at: datetime
    conversion_value: float = 0.0
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class LearningCandidate:
    candidate_id: str
    strategy_id: str
    experiment_id: str
    content_id: str
    metric: str
    baseline: float
    observed: float
    lift: float
    attribution: AttributionResult
    proposal: LearningProposal
    evidence_event_ids: tuple[str, ...]
    status: str = "candidate"


@dataclass(frozen=True)
class LiveLearningResult:
    events_added: int
    metrics_added: int
    content_genome: ContentGenome
    experiment_result: ExperimentResult
    attribution: AttributionResult
    learning_candidate: LearningCandidate


def build_learning_candidate(
    *,
    strategy_id: str,
    experiment: ExperimentSpec,
    content_id: str,
    experiment_result: ExperimentResult,
    attribution: AttributionResult,
    evidence_event_ids: tuple[str, ...],
) -> LearningCandidate:
    """Convert a measured experiment into a reversible learning candidate."""
    observed = max((value for _, value in experiment_result.variant_values), default=experiment_result.control_value)
    learning = propose_learning(
        LearningObservation(
            strategy_id=strategy_id,
            metric=experiment_result.metric,
            baseline=experiment_result.control_value,
            observed=observed,
            sample_size=1 if not experiment_result.sufficient_sample else 30,
        )
    )
    return LearningCandidate(
        candidate_id=str(uuid4()),
        strategy_id=strategy_id,
        experiment_id=experiment.experiment_id,
        content_id=content_id,
        metric=experiment_result.metric,
        baseline=experiment_result.control_value,
        observed=observed,
        lift=experiment_result.lift,
        attribution=attribution,
        proposal=learning,
        evidence_event_ids=evidence_event_ids,
    )


def run_live_learning_loop(
    *,
    observations: list[ChatObservation],
    event_store: SocialEventStore,
    experiment: ExperimentSpec,
    experiment_observations: list[ExperimentObservation],
    strategy_id: str,
    content_id: str,
    genome_observations: list[ModalityObservation],
    conversion_id: str,
    conversion_value: float,
    touchpoints: list[AttributionTouchpoint],
    analytics_store: Any | None = None,
) -> LiveLearningResult:
    """Execute one evidence-backed learning cycle.

    The caller supplies observed facts. The function never manufactures
    platform metrics, conversions, or attribution touchpoints.
    """
    events, events_added, metrics_added = ingest_chat_observations(
        observations, event_store, analytics_store
    )
    genome = build_content_genome(content_id=content_id, observations=genome_observations)
    experiment_result = evaluate_experiment(experiment, experiment_observations)
    attribution = linear_attribution(conversion_id, touchpoints, conversion_value)
    candidate = build_learning_candidate(
        strategy_id=strategy_id,
        experiment=experiment,
        content_id=content_id,
        experiment_result=experiment_result,
        attribution=attribution,
        evidence_event_ids=tuple(event.event_id for event in events),
    )
    return LiveLearningResult(
        events_added=events_added,
        metrics_added=metrics_added,
        content_genome=genome,
        experiment_result=experiment_result,
        attribution=attribution,
        learning_candidate=candidate,
    )

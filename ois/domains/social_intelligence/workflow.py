"""Reference Social Intelligence lifecycle workflow.

This module is deterministic orchestration logic. The OIS Supervisor, Policy
Engine, Runtime, checkpointing, evidence, and recovery layers remain authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .analytics import PerformanceSummary, SocialMetric, summarize_metrics
from .fabric import InMemorySocialEventStore, SocialSignal, Trend, build_signals, detect_trends
from .intelligence import ContentGenome
from .learning import LearningEvent, PerformanceObservation, compare_prediction_to_outcome
from .prediction import Prediction, predict_content


@dataclass(frozen=True)
class SocialIntelligenceResult:
    signals: tuple[SocialSignal, ...]
    trends: tuple[Trend, ...]
    prediction: Prediction | None
    performance: PerformanceSummary
    learning: LearningEvent | None
    lifecycle: tuple[str, ...]


class SocialIntelligenceWorkflow:
    """Compose the Social Intelligence lifecycle without owning execution authority."""

    def __init__(self, store: InMemorySocialEventStore) -> None:
        self.store = store

    def observe_and_predict(self, genome: ContentGenome | None = None) -> SocialIntelligenceResult:
        events = self.store.list()
        signals = build_signals(events)
        trends = detect_trends(events)
        prediction = predict_content(genome) if genome is not None else None
        return SocialIntelligenceResult(
            signals=signals,
            trends=trends,
            prediction=prediction,
            performance=PerformanceSummary(0),
            learning=None,
            lifecycle=("observe", "normalize", "signal", "trend", "predict"),
        )

    def measure_and_learn(
        self,
        *,
        prediction: Prediction,
        observed: PerformanceObservation,
        metrics: list[SocialMetric] | None = None,
        evidence_refs: tuple[str, ...] = (),
    ) -> SocialIntelligenceResult:
        performance = summarize_metrics(metrics or [])
        learning = compare_prediction_to_outcome(
            content_id=prediction.content_id,
            prediction_version=prediction.model_version,
            predicted=prediction.metrics,
            observed=observed,
            evidence_refs=evidence_refs or prediction.evidence,
        )
        return SocialIntelligenceResult(
            signals=(), trends=(), prediction=prediction,
            performance=performance, learning=learning,
            lifecycle=("measure", "attribute", "compare", "learn", "candidate"),
        )

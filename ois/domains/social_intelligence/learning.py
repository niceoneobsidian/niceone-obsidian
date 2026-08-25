"""M17 performance feedback and evidence-backed learning primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class PerformanceObservation:
    """Observed outcome for a previously predicted content metric."""

    content_id: str
    metrics: Mapping[str, float]
    source: str
    observed_at: str


@dataclass(frozen=True)
class LearningEvent:
    """Append-only learning evidence; it never mutates production strategy."""

    content_id: str
    prediction_version: str
    errors: Mapping[str, float]
    mean_absolute_error: float
    evidence_refs: tuple[str, ...]


def compare_prediction_to_outcome(
    *,
    content_id: str,
    prediction_version: str,
    predicted: Mapping[str, float],
    observed: PerformanceObservation,
    evidence_refs: tuple[str, ...] = (),
) -> LearningEvent:
    """Create a deterministic learning event from prediction vs. outcome.

    Metrics absent from either side are excluded rather than fabricated. The
    resulting event can be persisted by the existing OIS memory/learning layer.
    """
    shared = sorted(set(predicted).intersection(observed.metrics))
    errors = {key: observed.metrics[key] - predicted[key] for key in shared}
    mae = sum(abs(value) for value in errors.values()) / len(errors) if errors else 0.0
    return LearningEvent(
        content_id=content_id,
        prediction_version=prediction_version,
        errors=errors,
        mean_absolute_error=mae,
        evidence_refs=evidence_refs,
    )

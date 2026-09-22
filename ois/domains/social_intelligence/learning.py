"""M17 performance feedback plus the append-only empirical learning loop for G2."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from .outcomes import OutcomeLedger


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
    """Create a deterministic learning event from prediction vs. outcome."""

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


@dataclass(frozen=True)
class LearningExample:
    """A persisted prediction/outcome pair suitable for empirical evaluation."""

    content_id: str
    prediction_id: str
    metric: str
    predicted: float
    observed: float
    error: float
    model_version: str
    created_at: datetime


class LearningLoop:
    """Read-only bridge from the outcome ledger to learning examples."""

    def __init__(self, ledger: OutcomeLedger) -> None:
        self._ledger = ledger

    def examples(self, *, metric: str) -> tuple[LearningExample, ...]:
        rows = self._ledger._db.execute(
            """
            SELECT p.prediction_id, p.content_id, p.model_version, p.metrics, o.value
            FROM predictions p
            JOIN outcomes o ON p.content_id = o.content_id
            WHERE o.metric = ?
            """,
            (metric,),
        ).fetchall()
        out: list[LearningExample] = []
        for row in rows:
            predicted = json.loads(row["metrics"]).get(metric)
            if isinstance(predicted, int | float):
                out.append(
                    LearningExample(
                        row["content_id"],
                        row["prediction_id"],
                        metric,
                        float(predicted),
                        float(row["value"]),
                        float(predicted) - float(row["value"]),
                        row["model_version"],
                        datetime.now(UTC),
                    )
                )
        return tuple(out)

    def evaluation(self, *, metric: str):
        return self._ledger.calibrate(metric=metric)

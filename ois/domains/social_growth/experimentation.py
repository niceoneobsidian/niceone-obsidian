"""Deterministic experimentation primitives for Social Growth.

Experiments are specifications and measured comparisons only. Starting,
publishing, promotion, or rollback remains an OIS execution/policy concern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExperimentVariant:
    variant_id: str
    content_id: str
    label: str
    allocation: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    hypothesis: str
    metric: str
    control: ExperimentVariant
    variants: tuple[ExperimentVariant, ...]
    success_threshold: float = 0.0
    status: str = "draft"


@dataclass(frozen=True)
class ExperimentObservation:
    experiment_id: str
    variant_id: str
    metric: str
    value: float
    sample_size: int


@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str
    metric: str
    control_value: float
    variant_values: tuple[tuple[str, float], ...]
    winning_variant_id: str | None
    lift: float
    confidence: float
    sufficient_sample: bool


def evaluate_experiment(
    spec: ExperimentSpec,
    observations: list[ExperimentObservation],
    *,
    minimum_sample_size: int = 30,
) -> ExperimentResult:
    """Compare observed variants against control without making execution decisions."""
    control = next(
        (
            o
            for o in observations
            if o.variant_id == spec.control.variant_id and o.metric == spec.metric
        ),
        None,
    )
    if control is None:
        return ExperimentResult(
            spec.experiment_id,
            spec.metric,
            0.0,
            (),
            None,
            0.0,
            0.0,
            False,
        )

    variants = [
        o
        for o in observations
        if o.variant_id != spec.control.variant_id and o.metric == spec.metric
    ]
    values = tuple((o.variant_id, o.value) for o in variants)
    if not variants or control.value == 0:
        return ExperimentResult(
            spec.experiment_id,
            spec.metric,
            control.value,
            values,
            None,
            0.0,
            0.0,
            False,
        )

    winner = max(variants, key=lambda o: o.value)
    lift = (winner.value - control.value) / abs(control.value)
    sufficient = (
        control.sample_size >= minimum_sample_size
        and winner.sample_size >= minimum_sample_size
    )
    confidence = (
        min(1.0, min(control.sample_size, winner.sample_size) / 100.0)
        if sufficient
        else 0.0
    )
    winning_id = winner.variant_id if sufficient and lift >= spec.success_threshold else None
    return ExperimentResult(
        spec.experiment_id,
        spec.metric,
        control.value,
        values,
        winning_id,
        lift,
        confidence,
        sufficient,
    )

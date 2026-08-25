"""M16 creative simulation and experimentation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .intelligence import ContentGenome
from .prediction import Prediction, predict_content


@dataclass(frozen=True)
class CreativeVariant:
    """One controlled creative alternative."""

    variant_id: str
    genome: ContentGenome
    hypothesis: str


@dataclass(frozen=True)
class VariantScore:
    """Prediction result attached to an experiment arm."""

    variant_id: str
    expected_metrics: Mapping[str, float]
    confidence: float


@dataclass(frozen=True)
class Experiment:
    """Immutable experiment definition."""

    experiment_id: str
    objective: str
    hypothesis: str
    control_variant_id: str
    variants: tuple[CreativeVariant, ...]


def simulate_variants(experiment: Experiment) -> tuple[VariantScore, ...]:
    """Rank variants by expected overall performance without mutating production."""
    scores = []
    for variant in experiment.variants:
        prediction: Prediction = predict_content(variant.genome)
        scores.append(
            VariantScore(
                variant_id=variant.variant_id,
                expected_metrics=prediction.metrics,
                confidence=prediction.confidence,
            )
        )
    return tuple(
        sorted(
            scores,
            key=lambda item: item.expected_metrics.get("overall_performance", 0.0),
            reverse=True,
        )
    )

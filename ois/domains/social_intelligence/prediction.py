"""M15 creative performance prediction primitives.

This is a calibrated-contract foundation, not a claim of a trained viral model.
The scorer is deterministic and explicitly exposes confidence and evidence so a
future learned model can replace it without changing downstream contracts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .intelligence import ContentGenome


@dataclass(frozen=True)
class Prediction:
    """A versioned prediction with explicit confidence and feature evidence."""

    content_id: str
    model_id: str
    model_version: str
    metrics: Mapping[str, float]
    confidence: float
    evidence: tuple[str, ...]


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, value))


def _feature(genome: ContentGenome, group: Mapping[str, object], key: str) -> float:
    value = group.get(key, 0.0)
    return float(value) if isinstance(value, int | float) else 0.0


def predict_content(genome: ContentGenome) -> Prediction:
    """Produce a transparent baseline prediction from genome features.

    The baseline intentionally uses only supplied evidence. It does not infer
    platform behavior from absent data and therefore remains suitable as a
    contract/integration test oracle.
    """
    hook = _feature(genome, genome.hook, "strength")
    curiosity = _feature(genome, genome.hook, "curiosity")
    emotion = _feature(genome, genome.emotion, "intensity")
    pacing = _feature(genome, genome.temporal, "pacing")
    visual = _feature(genome, genome.visual, "hook_strength")
    audience_fit = _feature(genome, genome.audience_signals, "fit")
    shareability = _feature(genome, genome.emotion, "shareability")

    retention = _bounded(
        0.30 * hook
        + 0.20 * pacing
        + 0.20 * visual
        + 0.15 * curiosity
        + 0.15 * emotion
    )
    engagement = _bounded(
        0.25 * emotion
        + 0.25 * curiosity
        + 0.20 * shareability
        + 0.30 * audience_fit
    )
    follow = _bounded(
        0.45 * audience_fit + 0.25 * emotion + 0.15 * hook + 0.15 * curiosity
    )
    scroll_stop = _bounded(0.60 * hook + 0.25 * visual + 0.15 * curiosity)
    overall = _bounded(
        0.30 * scroll_stop
        + 0.35 * retention
        + 0.20 * engagement
        + 0.15 * follow
    )

    available = sum(
        bool(group)
        for group in (
            genome.hook,
            genome.visual,
            genome.audio,
            genome.temporal,
            genome.emotion,
            genome.audience_signals,
        )
    )
    confidence = _bounded(available / 6.0)
    evidence = tuple(
        name
        for name, group in (
            ("hook", genome.hook),
            ("visual", genome.visual),
            ("temporal", genome.temporal),
            ("emotion", genome.emotion),
            ("audience", genome.audience_signals),
        )
        if group
    )

    metrics = {
        "overall_performance": overall,
        "scroll_stop_probability": scroll_stop,
        "retention_probability": retention,
        "engagement_probability": engagement,
        "follow_probability": follow,
    }
    return Prediction(
        content_id=genome.content_id,
        model_id="ois.baseline.creative_predictor",
        model_version="m15.v1",
        metrics=metrics,
        confidence=confidence,
        evidence=evidence,
    )

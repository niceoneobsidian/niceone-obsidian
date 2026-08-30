"""Calibration and evaluation primitives for football probabilities."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class CalibrationMetrics:
    brier_score: float
    log_loss: float
    accuracy: float
    sample_count: int


def multiclass_brier(probabilities: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float:
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probabilities and outcomes must be non-empty and equal length")
    score = 0.0
    for probs, outcome in zip(probabilities, outcomes, strict=True):
        if len(probs) != 3 or outcome not in (0, 1, 2):
            raise ValueError("each prediction must contain 3 probabilities and outcome must be 0, 1, or 2")
        if any(p < 0 or p > 1 for p in probs) or abs(sum(probs) - 1.0) > 1e-6:
            raise ValueError("probabilities must be normalized")
        score += sum((p - (1.0 if i == outcome else 0.0)) ** 2 for i, p in enumerate(probs))
    return score / len(probabilities)


def multiclass_log_loss(probabilities: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float:
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probabilities and outcomes must be non-empty and equal length")
    total = 0.0
    for probs, outcome in zip(probabilities, outcomes, strict=True):
        if len(probs) != 3 or outcome not in (0, 1, 2):
            raise ValueError("each prediction must contain 3 probabilities and outcome must be 0, 1, or 2")
        total -= math.log(max(min(probs[outcome], 1.0), 1e-15))
    return total / len(probabilities)


def evaluate(probabilities: Sequence[Sequence[float]], outcomes: Sequence[int]) -> CalibrationMetrics:
    brier = multiclass_brier(probabilities, outcomes)
    logloss = multiclass_log_loss(probabilities, outcomes)
    accuracy = sum(max(range(3), key=probabilities[i].__getitem__) == outcomes[i] for i in range(len(outcomes))) / len(outcomes)
    return CalibrationMetrics(brier, logloss, accuracy, len(outcomes))


def reliability_bins(probabilities: Iterable[float], outcomes: Iterable[int], *, bins: int = 10) -> list[tuple[float, float, int]]:
    """Return (mean_probability, observed_frequency, count) calibration bins."""
    if bins < 2:
        raise ValueError("bins must be >= 2")
    grouped: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for probability, outcome in zip(probabilities, outcomes, strict=True):
        if not 0 <= probability <= 1:
            raise ValueError("probability must be between 0 and 1")
        index = min(int(probability * bins), bins - 1)
        grouped[index].append((probability, outcome))
    return [
        (sum(p for p, _ in group) / len(group), sum(y for _, y in group) / len(group), len(group))
        for group in grouped
        if group
    ]

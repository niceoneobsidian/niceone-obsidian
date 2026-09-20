"""Leakage-safe evaluation primitives for football forecasts."""

from __future__ import annotations

from dataclasses import dataclass
from math import log

from .schemas import FootballPrediction


@dataclass(frozen=True)
class CalibrationReport:
    count: int
    multiclass_brier: float
    log_loss: float
    accuracy: float


def evaluate_predictions(
    predictions: list[FootballPrediction], outcomes: list[str]
) -> CalibrationReport:
    """Evaluate aligned predictions without fitting or using future outcomes during prediction."""
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    if not predictions:
        return CalibrationReport(0, 0.0, 0.0, 0.0)
    brier = 0.0
    logloss = 0.0
    correct = 0
    for prediction, outcome in zip(predictions, outcomes, strict=True):
        probs = {"home": prediction.home_win, "draw": prediction.draw, "away": prediction.away_win}
        if outcome not in probs:
            raise ValueError(f"unsupported outcome: {outcome}")
        brier += sum((probs[name] - float(name == outcome)) ** 2 for name in probs)
        logloss -= log(max(probs[outcome], 1e-15))
        correct += int(prediction.outcome == outcome)
    n = len(predictions)
    return CalibrationReport(n, brier / n, logloss / n, correct / n)

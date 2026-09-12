"""Validated public evaluation API for Football Intelligence."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

from .origin import FixtureRecord, PredictionRecord, TeamStrengthModel, XGModel

OUTCOMES = ("home", "draw", "away")

@dataclass(frozen=True)
class EvaluationReport:
    count: int
    brier: float
    log_loss: float
    accuracy: float
    status: str


def _poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def _probs(hxg: float, axg: float) -> tuple[float, float, float]:
    values = [0.0, 0.0, 0.0]
    for hg in range(11):
        for ag in range(11):
            p = _poisson(hg, hxg) * _poisson(ag, axg)
            values[0 if hg > ag else 1 if hg == ag else 2] += p
    total = sum(values)
    return tuple(v / total for v in values)  # type: ignore[return-value]


def evaluate(predictions: list[PredictionRecord], outcomes: list[str]) -> EvaluationReport:
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must be aligned")
    if not predictions:
        return EvaluationReport(0, 0.0, 0.0, 0.0, "INSUFFICIENT_DATA")
    brier = logloss = correct = 0.0
    for prediction, outcome in zip(predictions, outcomes, strict=True):
        if outcome not in OUTCOMES:
            raise ValueError(f"unsupported outcome: {outcome}")
        probs = prediction.probabilities()
        brier += sum((probs[name] - float(name == outcome)) ** 2 for name in OUTCOMES)
        logloss -= math.log(max(probs[outcome], 1e-15))
        correct += float(max(probs, key=probs.get) == outcome)
    n = len(predictions)
    return EvaluationReport(n, brier / n, logloss / n, correct / n, "EVALUATED")


class ValidatedBacktestEngine:
    """Chronological backtest with strict pre-outcome state updates."""
    version = "football.backtest.v1"

    def run(self, fixtures: list[FixtureRecord]) -> EvaluationReport:
        model = TeamStrengthModel()
        xg = XGModel()
        predictions: list[PredictionRecord] = []
        outcomes: list[str] = []
        for fixture in sorted((f for f in fixtures if f.completed), key=lambda f: f.kickoff_at):
            home = model.snapshot(fixture.home_team_id)
            away = model.snapshot(fixture.away_team_id)
            hxg, axg = xg.predict(home, away)
            h, d, a = _probs(hxg, axg)
            predictions.append(PredictionRecord(fixture.fixture_id, datetime.now(UTC), self.version, h, d, a, hxg, axg, False))
            outcomes.append(fixture.outcome or "")
            model.update(fixture)
        return evaluate(predictions, outcomes)


class WalkForwardEngine:
    version = "football.walk_forward.v1"

    def run(self, fixtures: list[FixtureRecord], min_train: int = 20) -> EvaluationReport:
        ordered = sorted((f for f in fixtures if f.completed), key=lambda f: f.kickoff_at)
        if len(ordered) <= min_train:
            return EvaluationReport(0, 0.0, 0.0, 0.0, "INSUFFICIENT_DATA")
        model = TeamStrengthModel()
        xg = XGModel()
        predictions: list[PredictionRecord] = []
        outcomes: list[str] = []
        for index, fixture in enumerate(ordered):
            if index < min_train:
                model.update(fixture)
                continue
            home = model.snapshot(fixture.home_team_id)
            away = model.snapshot(fixture.away_team_id)
            hxg, axg = xg.predict(home, away)
            h, d, a = _probs(hxg, axg)
            predictions.append(PredictionRecord(fixture.fixture_id, datetime.now(UTC), self.version, h, d, a, hxg, axg, False))
            outcomes.append(fixture.outcome or "")
            model.update(fixture)
        return evaluate(predictions, outcomes)

"""Canonical F0-F12 Football Intelligence lifecycle for OIS integration."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from .origin import (
    FixtureRecord,
    PredictionRecord,
    ProbabilityCalibrator,
    TeamStrengthModel,
    XGModel,
    evidence_event,
    market_edge,
    no_vig_probabilities,
)


@dataclass(frozen=True)
class FootballRunResult:
    status: str
    stage: str
    predictions: tuple[PredictionRecord, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    metrics: dict[str, float] | None = None


@dataclass(frozen=True)
class FootballIntelligenceOrigin:
    """F0 contract + executable orchestration boundary.

    F1 provider ingestion is injected; F2 persistence is injected by the OIS store;
    F3-F9 are deterministic/statistical here; F10-F12 remain governed by OIS policy.
    """

    version: str = "football-origin-v1"

    def build_predictions(self, fixtures: Iterable[FixtureRecord]) -> FootballRunResult:
        ordered = sorted(fixtures, key=lambda f: f.kickoff_at)
        state = TeamStrengthModel()
        xg = XGModel()
        predictions: list[PredictionRecord] = []
        evidence: list[str] = []
        for fixture in ordered:
            if fixture.completed:
                # Only predict before updating with this fixture: no target leakage.
                home = state.snapshot(fixture.home_team_id)
                away = state.snapshot(fixture.away_team_id)
                hxg, axg = xg.predict(home, away)
                probs = _poisson_1x2(hxg, axg)
                prediction = PredictionRecord(
                    fixture.fixture_id, datetime.now(UTC), self.version,
                    *probs, hxg, axg, False,
                )
                predictions.append(prediction)
                state.update(fixture)
            else:
                home = state.snapshot(fixture.home_team_id)
                away = state.snapshot(fixture.away_team_id)
                hxg, axg = xg.predict(home, away)
                probs = _poisson_1x2(hxg, axg)
                predictions.append(PredictionRecord(
                    fixture.fixture_id, datetime.now(UTC), self.version,
                    *probs, hxg, axg, False,
                ))
            event = evidence_event("football.prediction", "ois.football", {
                "fixture_id": fixture.fixture_id, "model_version": self.version,
            })
            evidence.append(event.event_id)
        return FootballRunResult("COMPUTED", "F3-F5", tuple(predictions), tuple(evidence))

    def evaluate(self, predictions: list[PredictionRecord], outcomes: list[str]) -> FootballRunResult:
        if len(predictions) != len(outcomes):
            raise ValueError("predictions and outcomes must be aligned")
        if not predictions:
            return FootballRunResult("INSUFFICIENT_DATA", "F7-F8")
        brier = logloss = correct = 0.0
        for p, outcome in zip(predictions, outcomes, strict=True):
            probs = p.probabilities()
            brier += sum((probs[k] - float(k == outcome)) ** 2 for k in probs)
            logloss -= math.log(max(probs[outcome], 1e-15))
            correct += float(max(probs, key=probs.get) == outcome)
        n = len(predictions)
        metrics = {"count": float(n), "brier": brier / n, "log_loss": logloss / n, "accuracy": correct / n}
        event = evidence_event("football.evaluation", "ois.football", metrics)
        return FootballRunResult("EVALUATED", "F7-F9", (), (event.event_id,), metrics)

    def calibrate(self, predictions: list[PredictionRecord], outcomes: list[str]) -> tuple[ProbabilityCalibrator, FootballRunResult]:
        if len(predictions) != len(outcomes) or not predictions:
            return ProbabilityCalibrator(), FootballRunResult("INSUFFICIENT_DATA", "F5")
        calibrator = ProbabilityCalibrator()
        calibrator.fit([(p.home, p.draw, p.away) for p in predictions], outcomes)
        event = evidence_event("football.calibration", "ois.football", {"temperature": calibrator.temperature, "count": len(predictions)})
        return calibrator, FootballRunResult("CALIBRATED", "F5-F9", (), (event.event_id,), {"temperature": calibrator.temperature})

    @staticmethod
    def market(probabilities: tuple[float, float, float], odds: tuple[float | None, float | None, float | None]) -> dict[str, object]:
        return {"no_vig": no_vig_probabilities(odds), "edge": market_edge(probabilities, odds)}


def _poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def _poisson_1x2(home_xg: float, away_xg: float, max_goals: int = 10) -> tuple[float, float, float]:
    values = [0.0, 0.0, 0.0]
    for hg in range(max_goals + 1):
        for ag in range(max_goals + 1):
            p = _poisson(hg, home_xg) * _poisson(ag, away_xg)
            values[0 if hg > ag else 1 if hg == ag else 2] += p
    total = sum(values)
    return tuple(v / total for v in values)  # type: ignore[return-value]


def evolution_candidate(current: str, candidate: str, baseline: dict[str, float], challenger: dict[str, float]) -> dict[str, object]:
    proposal = f"{current}|{candidate}|{baseline}|{challenger}"
    return {
        "proposal_id": hashlib.sha256(proposal.encode()).hexdigest()[:32],
        "current_version": current,
        "candidate_version": candidate,
        "baseline": baseline,
        "challenger": challenger,
        "requires_approval": True,
        "reversible": True,
        "promotion_gate": "walk_forward + calibration + evidence + OIS policy approval",
    }

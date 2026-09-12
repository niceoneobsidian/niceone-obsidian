"""Football Intelligence Origin: F1-F12 governed domain primitives.

This module is intentionally dependency-light. It provides deterministic contracts and
reference implementations; external data, OIS persistence, execution policy, and model
promotion remain explicit integration boundaries.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from typing import Iterable, Protocol


OUTCOMES = ("home", "draw", "away")


@dataclass(frozen=True)
class FixtureRecord:
    fixture_id: str
    competition: str
    kickoff_at: datetime
    home_team_id: str
    home_team: str
    away_team_id: str
    away_team: str
    home_goals: int | None = None
    away_goals: int | None = None
    home_xg: float | None = None
    away_xg: float | None = None
    status: str = "scheduled"
    source_id: str = "unknown"
    observed_at: datetime = datetime(1970, 1, 1, tzinfo=UTC)

    @property
    def completed(self) -> bool:
        return self.home_goals is not None and self.away_goals is not None

    @property
    def outcome(self) -> str | None:
        if not self.completed:
            return None
        if self.home_goals > self.away_goals:
            return "home"
        if self.home_goals < self.away_goals:
            return "away"
        return "draw"


@dataclass(frozen=True)
class OddsSnapshot:
    fixture_id: str
    market: str
    home: float | None
    draw: float | None
    away: float | None
    captured_at: datetime
    bookmaker: str
    source_id: str


@dataclass(frozen=True)
class TeamRating:
    team_id: str
    elo: float
    attack: float
    defense: float
    xg_for: float
    xg_against: float
    matches: int


@dataclass(frozen=True)
class PredictionRecord:
    fixture_id: str
    created_at: datetime
    model_version: str
    home: float
    draw: float
    away: float
    expected_home_goals: float
    expected_away_goals: float
    abstain: bool
    evidence_ids: tuple[str, ...] = ()

    def probabilities(self) -> dict[str, float]:
        return {"home": self.home, "draw": self.draw, "away": self.away}


@dataclass(frozen=True)
class CalibrationReport:
    count: int
    brier: float
    log_loss: float
    accuracy: float
    calibration_error: float
    status: str


@dataclass(frozen=True)
class BacktestReport:
    count: int
    brier: float
    log_loss: float
    accuracy: float
    roi: float | None
    max_drawdown: float | None
    status: str


@dataclass(frozen=True)
class EvidenceEvent:
    event_id: str
    event_type: str
    observed_at: datetime
    source_id: str
    payload_hash: str
    payload: dict[str, object]


class FootballProvider(Protocol):
    provider_id: str

    def fixtures(self, start: datetime, end: datetime) -> Iterable[FixtureRecord]: ...

    def live(self) -> Iterable[FixtureRecord]: ...


class EvidenceSink(Protocol):
    def append(self, event: EvidenceEvent) -> None: ...


def _normalize(values: Iterable[float]) -> tuple[float, ...]:
    xs = [max(0.0, float(x)) for x in values]
    total = sum(xs)
    if total <= 0:
        return tuple(1.0 / len(xs) for _ in xs)
    return tuple(x / total for x in xs)


def _poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def _poisson_1x2(home_xg: float, away_xg: float, max_goals: int = 10) -> tuple[float, float, float]:
    home = draw = away = 0.0
    for hg in range(max_goals + 1):
        for ag in range(max_goals + 1):
            p = _poisson(hg, home_xg) * _poisson(ag, away_xg)
            if hg > ag:
                home += p
            elif hg == ag:
                draw += p
            else:
                away += p
    return _normalize((home, draw, away))  # type: ignore[return-value]


class TeamStrengthModel:
    """Leakage-safe Elo + attack/defence state updated only after completed fixtures."""

    def __init__(self, k: float = 20.0, home_advantage: float = 55.0) -> None:
        self.k = k
        self.home_advantage = home_advantage
        self._ratings: dict[str, float] = {}
        self._goals_for: dict[str, list[float]] = {}
        self._goals_against: dict[str, list[float]] = {}
        self._xg_for: dict[str, list[float]] = {}
        self._xg_against: dict[str, list[float]] = {}
        self._matches: dict[str, int] = {}

    def rating(self, team_id: str) -> float:
        return self._ratings.get(team_id, 1500.0)

    def update(self, fixture: FixtureRecord) -> None:
        if not fixture.completed:
            return
        home, away = fixture.home_team_id, fixture.away_team_id
        expected = 1.0 / (1.0 + 10.0 ** (-(self.rating(home) - self.rating(away) + self.home_advantage) / 400.0))
        actual = 1.0 if fixture.home_goals > fixture.away_goals else 0.0 if fixture.home_goals < fixture.away_goals else 0.5
        delta = self.k * (actual - expected)
        self._ratings[home] = self.rating(home) + delta
        self._ratings[away] = self.rating(away) - delta
        self._goals_for.setdefault(home, []).append(float(fixture.home_goals))
        self._goals_for.setdefault(away, []).append(float(fixture.away_goals))
        self._goals_against.setdefault(home, []).append(float(fixture.away_goals))
        self._goals_against.setdefault(away, []).append(float(fixture.home_goals))
        self._xg_for.setdefault(home, []).append(float(fixture.home_xg if fixture.home_xg is not None else fixture.home_goals))
        self._xg_for.setdefault(away, []).append(float(fixture.away_xg if fixture.away_xg is not None else fixture.away_goals))
        self._xg_against.setdefault(home, []).append(float(fixture.away_xg if fixture.away_xg is not None else fixture.away_goals))
        self._xg_against.setdefault(away, []).append(float(fixture.home_xg if fixture.home_xg is not None else fixture.home_goals))
        self._matches[home] = self._matches.get(home, 0) + 1
        self._matches[away] = self._matches.get(away, 0) + 1

    def snapshot(self, team_id: str) -> TeamRating:
        gf = self._goals_for.get(team_id, [1.4])
        ga = self._goals_against.get(team_id, [1.4])
        xf = self._xg_for.get(team_id, gf)
        xa = self._xg_against.get(team_id, ga)
        return TeamRating(team_id, self.rating(team_id), statistics.fmean(gf), statistics.fmean(ga), statistics.fmean(xf), statistics.fmean(xa), self._matches.get(team_id, 0))


class XGModel:
    """Baseline xG model using attack/defence state; learned replacements share this contract."""

    version = "football.xg.baseline.v1"

    def predict(self, home: TeamRating, away: TeamRating) -> tuple[float, float]:
        home_xg = max(0.05, 0.55 * home.xg_for + 0.45 * away.xg_against)
        away_xg = max(0.05, 0.55 * away.xg_for + 0.45 * home.xg_against)
        home_xg *= 1.08
        return home_xg, away_xg


class ProbabilityCalibrator:
    """Multiclass temperature scaling fitted on a historical validation window."""

    def __init__(self, temperature: float = 1.0) -> None:
        self.temperature = max(0.05, temperature)

    def fit(self, probabilities: list[tuple[float, float, float]], outcomes: list[str]) -> None:
        if len(probabilities) != len(outcomes) or not probabilities:
            raise ValueError("calibration data must be non-empty and aligned")
        best_t, best_loss = 1.0, float("inf")
        for i in range(5, 401):
            t = i / 100.0
            loss = 0.0
            for p, outcome in zip(probabilities, outcomes, strict=True):
                q = _normalize(math.exp(math.log(max(x, 1e-12)) / t) for x in p)
                loss -= math.log(max(q[OUTCOMES.index(outcome)], 1e-15))
            if loss < best_loss:
                best_t, best_loss = t, loss
        self.temperature = best_t

    def transform(self, p: tuple[float, float, float]) -> tuple[float, float, float]:
        return _normalize(math.exp(math.log(max(x, 1e-12)) / self.temperature) for x in p)  # type: ignore[return-value]


def calibration_report(predictions: list[PredictionRecord], outcomes: list[str]) -> CalibrationReport:
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must be aligned")
    if not predictions:
        return CalibrationReport(0, 0.0, 0.0, 0.0, 0.0, "INSUFFICIENT_DATA")
    brier = logloss = correct = 0.0
    bins: list[list[float]] = [[] for _ in range(10)]
    for pred, outcome in zip(predictions, outcomes, strict=True):
        probs = pred.probabilities()
        brier += sum((probs[k] - float(k == outcome)) ** 2 for k in OUTCOMES)
        logloss -= math.log(max(probs[outcome], 1e-15))
        correct += float(predicted := max(probs, key=probs.get)) == float(outcome == predicted)
        p = probs[outcome]
        bins[min(9, int(p * 10))].append(float(p == 1.0))
    ece = 0.0
    for bucket in bins:
        if bucket:
            ece += len(bucket) / len(predictions) * abs(statistics.fmean(bucket) - 0.5)
    n = len(predictions)
    return CalibrationReport(n, brier / n, logloss / n, correct / n, ece, "EVALUATED")


def no_vig_probabilities(odds: tuple[float | None, float | None, float | None]) -> tuple[float, float, float] | None:
    if any(x is None or x <= 1.0 for x in odds):
        return None
    return _normalize(1.0 / odds[0], 1.0 / odds[1], 1.0 / odds[2])  # type: ignore[operator,return-value]


def market_edge(model: tuple[float, float, float], odds: tuple[float | None, float | None, float | None]) -> dict[str, float]:
    fair = no_vig_probabilities(odds)
    if fair is None:
        return {}
    return {k: model[i] - fair[i] for i, k in enumerate(OUTCOMES)}


class BacktestEngine:
    """Chronological backtest. It updates team state strictly after each observed outcome."""

    def __init__(self, model: TeamStrengthModel | None = None) -> None:
        self.model = model or TeamStrengthModel()
        self.xg = XGModel()

    def predict(self, fixture: FixtureRecord) -> PredictionRecord:
        home = self.model.snapshot(fixture.home_team_id)
        away = self.model.snapshot(fixture.away_team_id)
        hxg, axg = self.xg.predict(home, away)
        h, d, a = _poisson_1x2(hxg, axg)
        return PredictionRecord(fixture.fixture_id, datetime.now(UTC), self.xg.version, h, d, a, hxg, axg, False)

    def run(self, fixtures: Iterable[FixtureRecord]) -> BacktestReport:
        ordered = sorted((f for f in fixtures if f.completed), key=lambda f: f.kickoff_at)
        predictions: list[PredictionRecord] = []
        outcomes: list[str] = []
        for fixture in ordered:
            prediction = self.predict(fixture)
            predictions.append(prediction)
            outcomes.append(fixture.outcome or "")
            self.model.update(fixture)
        report = calibration_report(predictions, outcomes)
        return BacktestReport(report.count, report.brier, report.log_loss, report.accuracy, None, None, report.status)


class WalkForwardEvaluator:
    """Expanding-window evaluation with a clean fit/predict boundary."""

    def evaluate(self, fixtures: list[FixtureRecord], min_train: int = 20) -> BacktestReport:
        ordered = sorted((f for f in fixtures if f.completed), key=lambda f: f.kickoff_at)
        if len(ordered) <= min_train:
            return BacktestReport(0, 0.0, 0.0, 0.0, None, None, "INSUFFICIENT_DATA")
        model = TeamStrengthModel()
        preds: list[PredictionRecord] = []
        outcomes: list[str] = []
        for index, fixture in enumerate(ordered):
            if index < min_train:
                model.update(fixture)
                continue
            home, away = model.snapshot(fixture.home_team_id), model.snapshot(fixture.away_team_id)
            hxg, axg = XGModel().predict(home, away)
            h, d, a = _poisson_1x2(hxg, axg)
            preds.append(PredictionRecord(fixture.fixture_id, datetime.now(UTC), "football.xg.baseline.v1", h, d, a, hxg, axg, False))
            outcomes.append(fixture.outcome or "")
            model.update(fixture)
        report = calibration_report(preds, outcomes)
        return BacktestReport(report.count, report.brier, report.log_loss, report.accuracy, None, None, "WALK_FORWARD_EVALUATED")


def evidence_event(event_type: str, source_id: str, payload: dict[str, object]) -> EvidenceEvent:
    raw = json.dumps(payload, sort_keys=True, default=str).encode()
    digest = hashlib.sha256(raw).hexdigest()
    event_id = hashlib.sha256(f"{event_type}|{source_id}|{digest}".encode()).hexdigest()[:32]
    return EvidenceEvent(event_id, event_type, datetime.now(UTC), source_id, digest, payload)


@dataclass(frozen=True)
class SupervisorDecision:
    action: str
    reason: str
    capability: str
    evidence_required: bool = True


class FootballSupervisor:
    """Policy-facing router. It never executes external side effects itself."""

    def route(self, intent: str, validated: bool = False) -> SupervisorDecision:
        text = intent.lower()
        if "live" in text:
            return SupervisorDecision("route", "live intelligence requested", "football.live_update")
        if "backtest" in text or "walk-forward" in text:
            return SupervisorDecision("route", "evaluation requested", "football.backtest")
        if "odds" in text or "market" in text:
            return SupervisorDecision("route", "market intelligence requested", "football.market")
        if "predict" in text or "forecast" in text:
            if not validated:
                return SupervisorDecision("abstain", "prediction path requires validation gate", "football.predict_1x2")
            return SupervisorDecision("route", "prediction requested", "football.predict_1x2")
        return SupervisorDecision("research", "unclassified football intent", "football.research")


@dataclass(frozen=True)
class DashboardSnapshot:
    generated_at: datetime
    fixtures: int
    live: int
    predictions: int
    evaluated: int
    model_version: str
    validation_status: str


@dataclass(frozen=True)
class EvolutionProposal:
    proposal_id: str
    current_version: str
    candidate_version: str
    evidence: dict[str, float]
    requires_approval: bool = True
    reversible: bool = True


def dashboard_snapshot(fixtures: Iterable[FixtureRecord], predictions: Iterable[PredictionRecord], evaluated: int, model_version: str, validation_status: str) -> DashboardSnapshot:
    rows = list(fixtures)
    return DashboardSnapshot(datetime.now(UTC), len(rows), sum(f.status in {"live", "inplay"} for f in rows), len(list(predictions)), evaluated, model_version, validation_status)


def propose_evolution(current_version: str, candidate_version: str, baseline: BacktestReport, candidate: BacktestReport) -> EvolutionProposal:
    evidence = {"baseline_brier": baseline.brier, "candidate_brier": candidate.brier, "brier_delta": baseline.brier - candidate.brier, "baseline_accuracy": baseline.accuracy, "candidate_accuracy": candidate.accuracy}
    return EvolutionProposal(hashlib.sha256(f"{current_version}|{candidate_version}|{evidence}".encode()).hexdigest()[:32], current_version, candidate_version, evidence)


__all__ = [
    "BacktestEngine", "BacktestReport", "CalibrationReport", "DashboardSnapshot", "EvidenceEvent",
    "EvolutionProposal", "FixtureRecord", "FootballProvider", "FootballSupervisor", "OddsSnapshot",
    "PredictionRecord", "ProbabilityCalibrator", "TeamRating", "TeamStrengthModel", "WalkForwardEvaluator",
    "XGModel", "calibration_report", "dashboard_snapshot", "evidence_event", "market_edge", "no_vig_probabilities",
    "propose_evolution",
]

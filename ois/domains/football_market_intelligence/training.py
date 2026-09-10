"""Provider-backed, leakage-safe training for the seven football markets.

The trainer consumes prediction-time snapshots produced by the football feed
plane. Each market is fitted independently; no trained market borrows fitted
parameters from another market. Training artifacts carry source/model versions
and are intended for governed promotion by OIS.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from statistics import mean
from typing import Iterable, Sequence

from .models import MatchFeatures, MarketFamily, _clamp, fair_odds, poisson_cdf, score_matrix
from .pipeline import FeatureSnapshot


@dataclass(frozen=True)
class TrainingRow:
    """One chronological, prediction-time-safe row and its market outcomes."""

    match_id: str
    as_of_rank: int
    features: MatchFeatures
    home_goals: int
    away_goals: int
    corners: int | None = None
    cards: int | None = None
    player_shots: int | None = None
    player_sot: int | None = None
    player_scored: int | None = None
    live_goal: int | None = None


@dataclass(frozen=True)
class FittedGoalModel:
    home_rate: float
    away_rate: float
    model_id: str = "football-goals-fitted-v1"

    def predict(self, features: MatchFeatures, line: float = 2.5) -> dict[str, float]:
        matrix = score_matrix(self.home_rate, self.away_rate)
        over = sum(p for h, row in enumerate(matrix) for a, p in enumerate(row) if h + a > line)
        btts = sum(p for h, row in enumerate(matrix) for a, p in enumerate(row) if h > 0 and a > 0)
        return {"over": over, "under": 1 - over, "btts_yes": btts, "btts_no": 1 - btts}


@dataclass(frozen=True)
class FittedResultModel:
    home_logit: float
    draw_logit: float
    away_logit: float
    model_id: str = "football-result-fitted-v1"

    def predict(self, _: MatchFeatures) -> dict[str, float]:
        values = [exp(self.home_logit), exp(self.draw_logit), exp(self.away_logit)]
        total = sum(values)
        return {"home": values[0] / total, "draw": values[1] / total, "away": values[2] / total}


@dataclass(frozen=True)
class FittedCountModel:
    family: MarketFamily
    rate: float
    model_id: str

    def predict(self, line: float) -> dict[str, float]:
        under = poisson_cdf(self.rate, int(line))
        return {"over": 1 - under, "under": under}


@dataclass(frozen=True)
class FittedShotModel:
    shot_rate: float
    sot_rate: float
    model_id: str = "football-shots-fitted-v1"

    def predict(self, line: float = 1.5) -> dict[str, float]:
        return {
            "shots_over": 1 - poisson_cdf(self.shot_rate, int(line)),
            "shots_under": poisson_cdf(self.shot_rate, int(line)),
            "sot_over": 1 - poisson_cdf(self.sot_rate, int(line)),
        }


@dataclass(frozen=True)
class FittedPlayerGoalModel:
    scoring_rate: float
    model_id: str = "football-player-goal-fitted-v1"

    def predict(self) -> float:
        return 1 - exp(-max(0.0, self.scoring_rate))


@dataclass(frozen=True)
class FittedLiveModel:
    goal_hazard_per_minute: float
    model_id: str = "football-live-state-fitted-v1"

    def predict(self, features: MatchFeatures) -> dict[str, float]:
        hazard = max(0.0, self.goal_hazard_per_minute * max(0, features.remaining_minutes))
        return {"next_goal_yes": 1 - exp(-hazard), "next_goal_no": exp(-hazard)}


@dataclass(frozen=True)
class FittedFootballModels:
    goal: FittedGoalModel
    result: FittedResultModel
    corner: FittedCountModel
    card: FittedCountModel
    shot: FittedShotModel
    player_goal: FittedPlayerGoalModel
    live: FittedLiveModel
    training_rows: int
    source_versions: tuple[str, ...]


def rows_from_snapshots(snapshots: Sequence[FeatureSnapshot], outcomes: dict[str, dict[str, int]]) -> tuple[TrainingRow, ...]:
    """Join prediction-time feature snapshots to outcomes by canonical match id."""
    rows: list[TrainingRow] = []
    for rank, snapshot in enumerate(sorted(snapshots, key=lambda s: s.as_of)):
        outcome = outcomes.get(snapshot.match_id)
        if outcome is None:
            continue
        rows.append(
            TrainingRow(
                match_id=snapshot.match_id,
                as_of_rank=rank,
                features=snapshot.features,
                home_goals=outcome["home_goals"],
                away_goals=outcome["away_goals"],
                corners=outcome.get("corners"),
                cards=outcome.get("cards"),
                player_shots=outcome.get("player_shots"),
                player_sot=outcome.get("player_sot"),
                player_scored=outcome.get("player_scored"),
                live_goal=outcome.get("live_goal"),
            )
        )
    return tuple(rows)


def fit_seven_models(rows: Sequence[TrainingRow]) -> FittedFootballModels:
    """Fit all seven market families independently from chronological rows."""
    if not rows:
        raise ValueError("at least one training row is required")
    ordered = sorted(rows, key=lambda row: row.as_of_rank)

    # Goal: independent Poisson MLEs on historical goal counts.
    goal = FittedGoalModel(
        home_rate=max(0.01, mean(row.home_goals for row in ordered)),
        away_rate=max(0.01, mean(row.away_goals for row in ordered)),
    )

    # Result: independent categorical MLE, with Laplace smoothing.
    counts = {"home": 1.0, "draw": 1.0, "away": 1.0}
    for row in ordered:
        key = "home" if row.home_goals > row.away_goals else "draw" if row.home_goals == row.away_goals else "away"
        counts[key] += 1
    result = FittedResultModel(*(log(counts[key]) for key in ("home", "draw", "away")))

    def fitted_count(values: Iterable[int | None], family: MarketFamily, model_id: str) -> FittedCountModel:
        observed = [float(value) for value in values if value is not None]
        if not observed:
            raise ValueError(f"no observations for {family.value}")
        return FittedCountModel(family, max(0.01, mean(observed)), model_id)

    corner = fitted_count((row.corners for row in ordered), MarketFamily.CORNERS, "football-corners-fitted-v1")
    card = fitted_count((row.cards for row in ordered), MarketFamily.CARDS, "football-cards-fitted-v1")
    shot_values = [float(row.player_shots) for row in ordered if row.player_shots is not None]
    sot_values = [float(row.player_sot) for row in ordered if row.player_sot is not None]
    shot = FittedShotModel(max(0.01, mean(shot_values)), max(0.01, mean(sot_values))) if shot_values and sot_values else (_raise_missing("shot"))

    scored = [int(row.player_scored) for row in ordered if row.player_scored is not None]
    player_goal = FittedPlayerGoalModel(max(0.0, sum(scored) / max(1, len(scored)))) if scored else (_raise_missing("player goal"))

    live = [int(row.live_goal) for row in ordered if row.live_goal is not None]
    live_model = FittedLiveModel(max(1e-6, sum(live) / max(1, len(live) * 90))) if live else (_raise_missing("live"))

    return FittedFootballModels(goal, result, corner, card, shot, player_goal, live_model, len(ordered), ("provider-snapshots-v1",))


def _raise_missing(name: str):
    raise ValueError(f"no observations for {name} market")


def binary_calibration_rows(probabilities: Sequence[float], outcomes: Sequence[int]) -> list[tuple[float, int]]:
    """Return chronological rows suitable for the existing OIS walk-forward gate."""
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have equal length")
    return [(_clamp(float(p), 1e-6, 1 - 1e-6), int(y)) for p, y in zip(probabilities, outcomes)]

"""Market-specific football probability engines.

The module deliberately separates probability generation by market family.  The
engines are deterministic reference implementations; fitted parameters and
provider-derived features can be supplied by the feature/training pipeline.
No model claims to create a betting edge without out-of-sample validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import exp, factorial
from typing import Iterable, Sequence


class MarketFamily(StrEnum):
    GOALS = "goals"
    RESULT = "result"
    CORNERS = "corners"
    CARDS = "cards"
    SHOTS = "shots"
    PLAYER_GOALS = "player_goals"
    LIVE = "live"


@dataclass(frozen=True)
class MatchFeatures:
    """Prediction-time features available strictly at ``as_of``."""

    home_attack: float
    home_defense: float
    away_attack: float
    away_defense: float
    home_advantage: float = 1.0
    expected_corners: float = 10.0
    expected_cards: float = 4.0
    player_goal_rate: float = 0.0
    player_shot_rate: float = 0.0
    player_sot_rate: float = 0.0
    elapsed_minute: int = 0
    remaining_minutes: int = 90
    home_goals: int = 0
    away_goals: int = 0


@dataclass(frozen=True)
class MarketProbability:
    family: MarketFamily
    selection: str
    probability: float
    fair_odds: float
    model_id: str
    line: float | None = None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def poisson_pmf(rate: float, count: int) -> float:
    if rate < 0 or count < 0:
        raise ValueError("rate and count must be non-negative")
    return exp(-rate) * rate**count / factorial(count)


def poisson_cdf(rate: float, count: int) -> float:
    if count < 0:
        return 0.0
    return sum(poisson_pmf(rate, k) for k in range(count + 1))


def fair_odds(probability: float) -> float:
    if not 0.0 < probability <= 1.0:
        raise ValueError("probability must be in (0, 1]")
    return 1.0 / probability


def score_matrix(home_rate: float, away_rate: float, max_goals: int = 10) -> list[list[float]]:
    matrix = [[poisson_pmf(home_rate, h) * poisson_pmf(away_rate, a)
               for a in range(max_goals + 1)] for h in range(max_goals + 1)]
    total = sum(map(sum, matrix))
    return [[p / total for p in row] for row in matrix]


def _score_probability(matrix: Sequence[Sequence[float]], predicate) -> float:
    return sum(p for h, row in enumerate(matrix) for a, p in enumerate(row) if predicate(h, a))


class GoalModel:
    """Poisson score model producing totals, BTTS and team-goal probabilities."""

    model_id = "football-goals-poisson-v1"

    def rates(self, features: MatchFeatures) -> tuple[float, float]:
        home = max(0.05, exp(features.home_attack + features.away_defense) * features.home_advantage)
        away = max(0.05, exp(features.away_attack + features.home_defense))
        return home, away

    def predict(self, features: MatchFeatures, total_line: float = 2.5) -> list[MarketProbability]:
        home_rate, away_rate = self.rates(features)
        matrix = score_matrix(home_rate, away_rate)
        over = _score_probability(matrix, lambda h, a: h + a > total_line)
        btts = _score_probability(matrix, lambda h, a: h > 0 and a > 0)
        home_over = 1 - poisson_cdf(home_rate, int(total_line))
        away_over = 1 - poisson_cdf(away_rate, int(total_line))
        return [
            MarketProbability(MarketFamily.GOALS, "over", over, fair_odds(over), self.model_id, total_line),
            MarketProbability(MarketFamily.GOALS, "under", 1 - over, fair_odds(1 - over), self.model_id, total_line),
            MarketProbability(MarketFamily.GOALS, "btts_yes", btts, fair_odds(btts), self.model_id),
            MarketProbability(MarketFamily.GOALS, "btts_no", 1 - btts, fair_odds(1 - btts), self.model_id),
            MarketProbability(MarketFamily.GOALS, "home_team_over", home_over, fair_odds(home_over), self.model_id, total_line),
            MarketProbability(MarketFamily.GOALS, "away_team_over", away_over, fair_odds(away_over), self.model_id, total_line),
        ]


class ResultModel:
    """Derives 1X2, DNB and double chance from the same score distribution."""

    model_id = "football-result-scoreline-v1"

    def predict(self, features: MatchFeatures) -> list[MarketProbability]:
        home_rate, away_rate = GoalModel().rates(features)
        matrix = score_matrix(home_rate, away_rate)
        home = _score_probability(matrix, lambda h, a: h > a)
        draw = _score_probability(matrix, lambda h, a: h == a)
        away = _score_probability(matrix, lambda h, a: h < a)
        return [
            MarketProbability(MarketFamily.RESULT, "home", home, fair_odds(home), self.model_id),
            MarketProbability(MarketFamily.RESULT, "draw", draw, fair_odds(draw), self.model_id),
            MarketProbability(MarketFamily.RESULT, "away", away, fair_odds(away), self.model_id),
            MarketProbability(MarketFamily.RESULT, "dnb_home", home / (home + away), fair_odds(home / (home + away)), self.model_id),
            MarketProbability(MarketFamily.RESULT, "dnb_away", away / (home + away), fair_odds(away / (home + away)), self.model_id),
            MarketProbability(MarketFamily.RESULT, "double_chance_1x", home + draw, fair_odds(home + draw), self.model_id),
            MarketProbability(MarketFamily.RESULT, "double_chance_x2", draw + away, fair_odds(draw + away), self.model_id),
        ]


class CountMarketModel:
    """Reusable Poisson count model for corners and cards."""

    def __init__(self, family: MarketFamily, model_id: str, expected_count: float) -> None:
        self.family = family
        self.model_id = model_id
        self.expected_count = max(0.01, expected_count)

    def predict(self, line: float) -> list[MarketProbability]:
        threshold = int(line)
        under = poisson_cdf(self.expected_count, threshold)
        over = 1 - under
        return [
            MarketProbability(self.family, "over", over, fair_odds(over), self.model_id, line),
            MarketProbability(self.family, "under", under, fair_odds(under), self.model_id, line),
        ]


class CornerModel(CountMarketModel):
    def __init__(self, expected_count: float) -> None:
        super().__init__(MarketFamily.CORNERS, "football-corners-poisson-v1", expected_count)


class CardModel(CountMarketModel):
    def __init__(self, expected_count: float) -> None:
        super().__init__(MarketFamily.CARDS, "football-cards-poisson-v1", expected_count)


class ShotModel:
    """Player shot/SOT count model using exposure-adjusted Poisson rates."""

    model_id = "football-player-shots-poisson-v1"

    def predict(self, features: MatchFeatures, line: float = 1.5) -> list[MarketProbability]:
        rate = max(0.01, features.player_shot_rate)
        threshold = int(line)
        under = poisson_cdf(rate, threshold)
        over = 1 - under
        sot_rate = max(0.01, features.player_sot_rate)
        sot_over = 1 - poisson_cdf(sot_rate, threshold)
        return [
            MarketProbability(MarketFamily.SHOTS, "shots_over", over, fair_odds(over), self.model_id, line),
            MarketProbability(MarketFamily.SHOTS, "shots_under", under, fair_odds(under), self.model_id, line),
            MarketProbability(MarketFamily.SHOTS, "sot_over", sot_over, fair_odds(sot_over), self.model_id, line),
        ]


class PlayerGoalModel:
    """Anytime scorer model from an exposure-adjusted goal hazard."""

    model_id = "football-player-goal-hazard-v1"

    def predict(self, features: MatchFeatures) -> MarketProbability:
        probability = 1 - exp(-max(0.0, features.player_goal_rate))
        return MarketProbability(
            MarketFamily.PLAYER_GOALS, "anytime_scorer", probability,
            fair_odds(probability), self.model_id,
        )


class LiveStateModel:
    """Remaining-time Poisson model conditioned on the current score."""

    model_id = "football-live-state-poisson-v1"

    def predict(self, features: MatchFeatures, total_line: float = 2.5) -> list[MarketProbability]:
        remaining = max(0, features.remaining_minutes)
        factor = remaining / 90.0
        home_rate, away_rate = GoalModel().rates(features)
        home_rate *= factor
        away_rate *= factor
        current_total = features.home_goals + features.away_goals
        needed = max(0, int(total_line) + 1 - current_total)
        total_rate = home_rate + away_rate
        over = 1 - poisson_cdf(total_rate, needed - 1)
        next_goal = 1 - exp(-total_rate)
        return [
            MarketProbability(MarketFamily.LIVE, "live_over", over, fair_odds(over), self.model_id, total_line),
            MarketProbability(MarketFamily.LIVE, "next_goal_yes", next_goal, fair_odds(next_goal), self.model_id),
            MarketProbability(MarketFamily.LIVE, "next_goal_no", 1 - next_goal, fair_odds(1 - next_goal), self.model_id),
        ]


@dataclass(frozen=True)
class CalibratedProbability:
    raw: float
    calibrated: float
    method: str
    version: str


class IsotonicCalibrator:
    """Small dependency-free monotone calibrator for binary outcomes."""

    def __init__(self, probabilities: Iterable[float], outcomes: Iterable[int], version: str = "isotonic-v1") -> None:
        pairs = sorted((float(p), int(y)) for p, y in zip(probabilities, outcomes))
        if not pairs:
            raise ValueError("calibration data cannot be empty")
        blocks: list[list[float]] = []
        for p, y in pairs:
            blocks.append([p, p, float(y), 1.0])
            while len(blocks) >= 2 and blocks[-2][2] / blocks[-2][3] > blocks[-1][2] / blocks[-1][3]:
                right = blocks.pop()
                left = blocks.pop()
                blocks.append([left[0], right[1], left[2] + right[2], left[3] + right[3]])
        self._blocks = blocks
        self.version = version

    def calibrate(self, probability: float) -> CalibratedProbability:
        p = _clamp(probability)
        for lo, hi, successes, count in self._blocks:
            if p <= hi:
                value = successes / count
                return CalibratedProbability(p, _clamp(value), "isotonic", self.version)
        _, _, successes, count = self._blocks[-1]
        return CalibratedProbability(p, _clamp(successes / count), "isotonic", self.version)


@dataclass(frozen=True)
class MarketQuote:
    selection: str
    model_probability: float
    calibrated_probability: float
    odds: float
    fair_odds: float
    edge: float
    ev: float
    publish: bool
    reason: str


def price_market(
    selection: str,
    probability: float,
    odds: float,
    *,
    calibrator: IsotonicCalibrator | None = None,
    min_edge: float = 0.02,
    min_probability: float = 0.50,
) -> MarketQuote:
    if odds <= 1:
        raise ValueError("odds must be greater than 1")
    calibrated = calibrator.calibrate(probability).calibrated if calibrator else probability
    fair = fair_odds(calibrated)
    edge = calibrated - 1.0 / odds
    ev = calibrated * odds - 1.0
    publish = calibrated >= min_probability and edge >= min_edge
    reason = "publish" if publish else "abstain: insufficient calibrated edge/confidence"
    return MarketQuote(selection, probability, calibrated, odds, fair, edge, ev, publish, reason)


@dataclass(frozen=True)
class WalkForwardRow:
    index: int
    probability: float
    outcome: int
    brier: float
    log_loss: float


def walk_forward_binary(
    observations: Sequence[tuple[float, int]],
    min_train_size: int = 20,
) -> list[WalkForwardRow]:
    """Evaluate predictions strictly out-of-sample in chronological order."""
    if min_train_size < 1 or len(observations) <= min_train_size:
        return []
    rows: list[WalkForwardRow] = []
    for index in range(min_train_size, len(observations)):
        probability, outcome = observations[index]
        p = _clamp(probability, 1e-6, 1 - 1e-6)
        rows.append(
            WalkForwardRow(
                index=index,
                probability=p,
                outcome=int(outcome),
                brier=(p - outcome) ** 2,
                log_loss=-(outcome * __import__("math").log(p) + (1 - outcome) * __import__("math").log(1 - p)),
            )
        )
    return rows


@dataclass(frozen=True)
class AbstentionDecision:
    publish: bool
    reason: str
    checks: tuple[str, ...]


def abstain_or_publish(
    *,
    probability: float,
    fair_odds_value: float,
    market_odds: float | None,
    evidence_complete: bool,
    calibration_ready: bool,
    min_edge: float = 0.02,
) -> AbstentionDecision:
    checks = []
    if not evidence_complete:
        return AbstentionDecision(False, "abstain: incomplete evidence", tuple(checks + ["evidence"]))
    if not calibration_ready:
        return AbstentionDecision(False, "abstain: calibration not validated", tuple(checks + ["calibration"]))
    if market_odds is None:
        return AbstentionDecision(False, "abstain: market price unavailable", tuple(checks + ["price"]))
    edge = probability - 1.0 / market_odds
    if edge < min_edge:
        return AbstentionDecision(False, "abstain: edge below threshold", tuple(checks + ["edge"]))
    if fair_odds_value <= 1:
        return AbstentionDecision(False, "abstain: invalid fair price", tuple(checks + ["fair_price"]))
    return AbstentionDecision(True, "publish", tuple(checks + ["evidence", "calibration", "price", "edge"]))


@dataclass(frozen=True)
class FootballMarketModelSuite:
    goal: GoalModel
    result: ResultModel
    corner: CornerModel
    card: CardModel
    shot: ShotModel
    player_goal: PlayerGoalModel
    live: LiveStateModel

    @classmethod
    def from_features(cls, features: MatchFeatures) -> "FootballMarketModelSuite":
        return cls(
            goal=GoalModel(),
            result=ResultModel(),
            corner=CornerModel(features.expected_corners),
            card=CardModel(features.expected_cards),
            shot=ShotModel(),
            player_goal=PlayerGoalModel(),
            live=LiveStateModel(),
        )

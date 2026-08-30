"""Football model federation with deterministic weighting and abstention."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import pstdev

from .features import feature_completeness
from .models import DixonColesModel, EloModel, PoissonModel
from .schemas import FootballPrediction, MatchState, ModelProbability
from .simulation import simulate_match


def _weighted(values: list[tuple[ModelProbability, float]], field: str) -> float:
    total = sum(weight for _, weight in values)
    return sum(getattr(model, field) * weight for model, weight in values) / max(total, 1e-12)


def _normalize(home: float, draw: float, away: float) -> tuple[float, float, float]:
    total = max(home + draw + away, 1e-12)
    return home / total, draw / total, away / total


@dataclass(frozen=True)
class FootballEnsemble:
    """Governed reference ensemble; learned weights can later be promoted by evaluation."""

    version: str = "football-ensemble-v2"
    elo_weight: float = 0.20
    poisson_weight: float = 0.30
    dixon_coles_weight: float = 0.35
    market_weight: float = 0.15
    abstain_confidence_threshold: float = 0.45
    max_model_disagreement: float = 0.20
    simulation_iterations: int = 10_000

    def predict(self, match: MatchState, *, simulation_seed: int | None = None) -> FootballPrediction:
        models = [EloModel().predict(match), PoissonModel().predict(match), DixonColesModel().predict(match)]
        weights = [self.elo_weight, self.poisson_weight, self.dixon_coles_weight]
        weighted = list(zip(models, weights, strict=True))
        home = _weighted(weighted, "home")
        draw = _weighted(weighted, "draw")
        away = _weighted(weighted, "away")
        expected_home = _weighted(weighted, "expected_home_goals")
        expected_away = _weighted(weighted, "expected_away_goals")

        if match.market_home and match.market_draw and match.market_away:
            market = _normalize(1 / match.market_home, 1 / match.market_draw, 1 / match.market_away)
            blend = self.market_weight
            home = (1 - blend) * home + blend * market[0]
            draw = (1 - blend) * draw + blend * market[1]
            away = (1 - blend) * away + blend * market[2]
            home, draw, away = _normalize(home, draw, away)

        side_disagreement = [m.home for m in models]
        agreement = max(0.0, min(1.0, 1.0 - pstdev(side_disagreement) / 0.25))
        completeness = feature_completeness(match)
        evidence_quality = sum(e.confidence for e in match.evidence) / len(match.evidence) if match.evidence else 0.0
        confidence = max(0.0, min(1.0, 0.40 * agreement + 0.35 * completeness + 0.25 * evidence_quality))
        abstain = confidence < self.abstain_confidence_threshold or (1.0 - agreement) > self.max_model_disagreement
        reason = "low_confidence_or_high_model_disagreement" if abstain else None

        simulation = simulate_match(
            expected_home,
            expected_away,
            iterations=self.simulation_iterations,
            correlation=0.08,
            seed=simulation_seed,
        )
        return FootballPrediction(
            match_id=match.match_id,
            home_win=home,
            draw=draw,
            away_win=away,
            expected_home_goals=expected_home,
            expected_away_goals=expected_away,
            confidence=confidence,
            model_agreement=agreement,
            data_completeness=completeness,
            abstain=abstain,
            abstention_reason=reason,
            models=models,
            simulation=simulation,
            evidence=match.evidence,
            model_ensemble_version=self.version,
        )

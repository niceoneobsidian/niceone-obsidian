"""Football model federation with deterministic weighting and abstention."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import pstdev

from .models import DixonColesModel, EloModel, PoissonModel
from .schemas import FootballPrediction, MatchState, ModelProbability


def _weighted(values: list[tuple[ModelProbability, float]], field: str) -> float:
    total = sum(weight for _, weight in values)
    return sum(getattr(model, field) * weight for model, weight in values) / max(total, 1e-12)


@dataclass(frozen=True)
class FootballEnsemble:
    """Reference ensemble; learned weights can later be supplied by OIS evaluation."""

    version: str = "football-ensemble-v1"
    elo_weight: float = 0.25
    poisson_weight: float = 0.35
    dixon_coles_weight: float = 0.40
    abstain_confidence_threshold: float = 0.42
    max_model_disagreement: float = 0.20

    def predict(self, match: MatchState) -> FootballPrediction:
        models = [
            EloModel().predict(match),
            PoissonModel().predict(match),
            DixonColesModel().predict(match),
        ]
        weighted = list(zip(models, (self.elo_weight, self.poisson_weight, self.dixon_coles_weight), strict=True))
        home = _weighted(weighted, "home")
        draw = _weighted(weighted, "draw")
        away = _weighted(weighted, "away")
        expected_home = _weighted(weighted, "expected_home_goals")
        expected_away = _weighted(weighted, "expected_away_goals")

        probabilities = [m.home for m in models]
        agreement = max(0.0, min(1.0, 1.0 - pstdev(probabilities) / 0.25))
        data_completeness = self._data_completeness(match)
        confidence = max(0.0, min(1.0, 0.55 * agreement + 0.45 * data_completeness))
        abstain = confidence < self.abstain_confidence_threshold or (1.0 - agreement) > self.max_model_disagreement
        reason = None
        if abstain:
            reason = "low_confidence_or_high_model_disagreement"
        return FootballPrediction(
            match_id=match.match_id,
            home_win=home,
            draw=draw,
            away_win=away,
            expected_home_goals=expected_home,
            expected_away_goals=expected_away,
            confidence=confidence,
            model_agreement=agreement,
            data_completeness=data_completeness,
            abstain=abstain,
            abstention_reason=reason,
            models=models,
            evidence=match.evidence,
            model_ensemble_version=self.version,
        )

    @staticmethod
    def _data_completeness(match: MatchState) -> float:
        checks = [
            match.home.elo > 0,
            match.away.elo > 0,
            match.home.attack_strength > 0,
            match.away.attack_strength > 0,
            match.home.defense_strength > 0,
            match.away.defense_strength > 0,
            match.home.lineup_confidence > 0,
            match.away.lineup_confidence > 0,
        ]
        return sum(checks) / len(checks)

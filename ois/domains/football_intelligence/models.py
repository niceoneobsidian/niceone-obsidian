"""Deterministic football prediction baselines.

These are deliberately dependency-light reference models. More complex ML models
can implement the same probability contract and be registered later.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .schemas import MatchState, ModelProbability


def _normalize(home: float, draw: float, away: float) -> tuple[float, float, float]:
    total = max(home + draw + away, 1e-12)
    return home / total, draw / total, away / total


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def _result_from_goals(
    home_xg: float, away_xg: float, max_goals: int = 10
) -> tuple[float, float, float]:
    hp = [_poisson_pmf(i, home_xg) for i in range(max_goals + 1)]
    ap = [_poisson_pmf(i, away_xg) for i in range(max_goals + 1)]
    home = draw = away = 0.0
    for hg, ph in enumerate(hp):
        for ag, pa in enumerate(ap):
            p = ph * pa
            if hg > ag:
                home += p
            elif hg == ag:
                draw += p
            else:
                away += p
    return _normalize(home, draw, away)


@dataclass(frozen=True)
class EloModel:
    model_id: str = "football.elo.v1"
    home_advantage: float = 55.0
    scale: float = 400.0

    def predict(self, match: MatchState) -> ModelProbability:
        rating_gap = match.home.elo - match.away.elo + self.home_advantage
        home = 1.0 / (1.0 + 10.0 ** (-rating_gap / self.scale))
        draw = max(0.05, 0.28 - abs(rating_gap) / 1800.0)
        away = max(0.0, 1.0 - home - draw)
        home, draw, away = _normalize(home, draw, away)
        return ModelProbability(
            model_id=self.model_id,
            home=home,
            draw=draw,
            away=away,
            expected_home_goals=match.home.xg_for,
            expected_away_goals=match.away.xg_for,
        )


@dataclass(frozen=True)
class PoissonModel:
    model_id: str = "football.poisson.v1"
    home_base: float = 1.50
    away_base: float = 1.20

    def predict(self, match: MatchState) -> ModelProbability:
        home_xg = (
            self.home_base * match.home.attack_strength / max(match.away.defense_strength, 0.1)
        )
        away_xg = (
            self.away_base * match.away.attack_strength / max(match.home.defense_strength, 0.1)
        )
        home_xg *= 1.0 + match.home.home_advantage + match.tactical_factor * 0.05
        away_xg *= 1.0 - match.tactical_factor * 0.05
        home, draw, away = _result_from_goals(max(home_xg, 0.05), max(away_xg, 0.05))
        return ModelProbability(
            model_id=self.model_id,
            home=home,
            draw=draw,
            away=away,
            expected_home_goals=home_xg,
            expected_away_goals=away_xg,
        )


@dataclass(frozen=True)
class DixonColesModel(PoissonModel):
    model_id: str = "football.dixon_coles.v1"
    low_score_correction: float = 0.06

    def predict(self, match: MatchState) -> ModelProbability:
        base = super().predict(match)
        # Conservative low-score correction: increases draw mass while preserving
        # a normalized distribution. This is a reference implementation, not a
        # fitted league-specific Dixon-Coles parameter set.
        draw = min(1.0, base.draw + self.low_score_correction * (1.0 - base.draw))
        remaining = max(0.0, 1.0 - draw)
        side_total = max(base.home + base.away, 1e-12)
        home = remaining * base.home / side_total
        away = remaining * base.away / side_total
        return base.model_copy(update={"home": home, "draw": draw, "away": away})

"""Deterministic, point-in-time football feature engineering primitives."""
from __future__ import annotations

from math import exp

from .schemas import MatchState


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def build_feature_vector(match: MatchState) -> dict[str, float]:
    """Return a stable numeric pre-match feature vector from supplied state only."""
    elo_gap = (match.home.elo - match.away.elo) / 400.0
    attack_gap = match.home.attack_strength - match.away.attack_strength
    defense_gap = match.away.defense_strength - match.home.defense_strength
    xg_gap = match.home.xg_for - match.away.xg_for
    form_gap = match.home.recent_form - match.away.recent_form
    rest_gap = _clamp((match.home.rest_days - match.away.rest_days) / 7.0)
    squad_gap = match.home.squad_strength - match.away.squad_strength
    injury_gap = match.away.injuries_impact - match.home.injuries_impact
    sot_gap = (match.home.shots_on_target_for - match.away.shots_on_target_for) / 5.0
    possession_gap = (match.home.possession - match.away.possession) / 100.0
    market_gap = 0.0
    if match.market_home and match.market_away:
        market_gap = _clamp((1.0 / match.market_home) - (1.0 / match.market_away))
    market_move = 0.0
    if match.market_home and match.prior_market_home:
        market_move = _clamp(match.prior_market_home / match.market_home - 1.0)
    return {
        "elo_gap": elo_gap,
        "attack_gap": attack_gap,
        "defense_gap": defense_gap,
        "xg_gap": xg_gap,
        "form_gap": form_gap,
        "rest_gap": rest_gap,
        "squad_gap": squad_gap,
        "injury_gap": injury_gap,
        "shots_on_target_gap": sot_gap,
        "possession_gap": possession_gap,
        "home_advantage": match.home.home_advantage,
        "referee_factor": match.referee_factor,
        "weather_factor": match.weather_factor,
        "tactical_factor": match.tactical_factor,
        "travel_factor": match.travel_factor,
        "market_gap": market_gap,
        "market_home_move": market_move,
        "lineup_confidence_gap": match.home.lineup_confidence - match.away.lineup_confidence,
    }


def feature_completeness(match: MatchState) -> float:
    vector = build_feature_vector(match)
    checks = [
        vector["elo_gap"] != 0.0,
        vector["attack_gap"] != 0.0,
        vector["defense_gap"] != 0.0,
        vector["xg_gap"] != 0.0,
        vector["form_gap"] != 0.0,
        match.home.shots_on_target_for > 0 and match.away.shots_on_target_for > 0,
        match.home.possession > 0 and match.away.possession > 0,
        bool(match.evidence),
    ]
    return sum(checks) / len(checks)


def sigmoid(value: float) -> float:
    if value >= 0:
        z = exp(-value)
        return 1.0 / (1.0 + z)
    z = exp(value)
    return z / (1.0 + z)

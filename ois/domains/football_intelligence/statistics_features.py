"""Deterministic features derived from historical match/player observations.

Features are intentionally descriptive. They do not assert that any feature is
predictive; model calibration and promotion remain separate OIS concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean

from .statistics_sources import MatchStatistics, PlayerMatchStatistics


@dataclass(frozen=True, slots=True)
class TeamFeatureVector:
    team_id: str
    matches: int
    shots_for_avg: float
    shots_on_target_for_avg: float
    corners_for_avg: float
    possession_avg: float
    cards_avg: float
    xg_for_avg: float
    xg_against_avg: float


@dataclass(frozen=True, slots=True)
class PlayerFeatureVector:
    player_id: str
    player_name: str
    matches: int
    minutes_avg: float
    rating_avg: float
    shots_avg: float
    shots_on_target_avg: float
    goals_avg: float
    assists_avg: float
    key_passes_avg: float
    tackles_avg: float
    cards_avg: float


def _avg(values: list[float | None]) -> float:
    clean = [value for value in values if value is not None]
    return mean(clean) if clean else 0.0


def team_features(
    observations: list[MatchStatistics],
    *,
    as_of: datetime | None = None,
) -> TeamFeatureVector:
    """Aggregate only observations available at ``as_of``."""
    eligible = [
        item for item in observations
        if as_of is None or item.observed_at <= as_of
    ]
    team_id = eligible[0].team_id if eligible else ""
    return TeamFeatureVector(
        team_id=team_id,
        matches=len(eligible),
        shots_for_avg=_avg([item.shots_total for item in eligible]),
        shots_on_target_for_avg=_avg([item.shots_on_target for item in eligible]),
        corners_for_avg=_avg([item.corners for item in eligible]),
        possession_avg=_avg([item.possession_pct for item in eligible]),
        cards_avg=_avg([(item.yellow_cards or 0) + (item.red_cards or 0) for item in eligible]),
        xg_for_avg=_avg([item.xg for item in eligible]),
        xg_against_avg=0.0,
    )


def player_features(
    observations: list[PlayerMatchStatistics],
    *,
    as_of: datetime | None = None,
) -> PlayerFeatureVector:
    """Build a rolling player profile without using future observations."""
    eligible = [
        item for item in observations
        if as_of is None or item.observed_at <= as_of
    ]
    player_id = eligible[0].player_id if eligible else ""
    player_name = eligible[0].player_name if eligible else ""
    return PlayerFeatureVector(
        player_id=player_id,
        player_name=player_name,
        matches=len(eligible),
        minutes_avg=_avg([item.minutes for item in eligible]),
        rating_avg=_avg([item.rating for item in eligible]),
        shots_avg=_avg([item.shots for item in eligible]),
        shots_on_target_avg=_avg([item.shots_on_target for item in eligible]),
        goals_avg=_avg([item.goals for item in eligible]),
        assists_avg=_avg([item.assists for item in eligible]),
        key_passes_avg=_avg([item.key_passes for item in eligible]),
        tackles_avg=_avg([item.tackles for item in eligible]),
        cards_avg=_avg([(item.yellow_cards or 0) + (item.red_cards or 0) for item in eligible]),
    )


def player_market_features(
    observations: list[PlayerMatchStatistics],
    player_id: str,
    *,
    as_of: datetime,
) -> PlayerFeatureVector:
    """Select one player and construct a prediction-time feature vector."""
    return player_features(
        [item for item in observations if item.player_id == player_id],
        as_of=as_of,
    )

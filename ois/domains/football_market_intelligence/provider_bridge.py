"""Bridge live/historical football feed observations into the market feature store."""
from __future__ import annotations

from datetime import datetime
from typing import Mapping

from ois.domains.football_intelligence.feed_service import MatchFeatureSnapshot
from ois.domains.football_intelligence.feeds import PlayerStatFeed, TeamStatFeed

from .models import MatchFeatures
from .pipeline import FeatureSnapshot, HistoricalFeatureStore


_STAT_KEYS = {
    "shots": ("Total Shots", "shots", "total_shots"),
    "shots_on": ("Shots on Goal", "shots_on_goal", "shots_on_target"),
    "corners": ("Corner Kicks", "corners", "corner_kicks"),
    "cards": ("Yellow Cards", "yellow_cards", "cards"),
    "possession": ("Ball Possession", "possession", "ball_possession"),
}


def ingest_provider_snapshot(
    store: HistoricalFeatureStore,
    snapshot: MatchFeatureSnapshot,
    *,
    as_of: datetime | None = None,
) -> FeatureSnapshot:
    """Normalize one provider observation and append it to the market feature store."""
    observed_at = as_of or snapshot.observed_at
    features = _features(snapshot)
    evidence_ids = tuple(
        evidence.source_id
        for row in (*snapshot.team_statistics, *snapshot.player_statistics)
        for evidence in row.evidence
    )
    feature_snapshot = FeatureSnapshot(
        match_id=snapshot.match.match.provider_match_id,
        as_of=observed_at,
        features=features,
        evidence_ids=evidence_ids,
    )
    store.append(feature_snapshot)
    return feature_snapshot


def _features(snapshot: MatchFeatureSnapshot) -> MatchFeatures:
    match = snapshot.match.match
    home = match.home_team_id
    away = match.away_team_id
    home_stats = next((row for row in snapshot.team_statistics if row.team_id == home), None)
    away_stats = next((row for row in snapshot.team_statistics if row.team_id == away), None)
    home_shots = _number(home_stats, _STAT_KEYS["shots"])
    away_shots = _number(away_stats, _STAT_KEYS["shots"])
    home_corners = _number(home_stats, _STAT_KEYS["corners"])
    away_corners = _number(away_stats, _STAT_KEYS["corners"])
    home_cards = _number(home_stats, _STAT_KEYS["cards"])
    away_cards = _number(away_stats, _STAT_KEYS["cards"])
    player_shots = mean_player_stat(snapshot.player_statistics, "shots")
    player_sot = mean_player_stat(snapshot.player_statistics, "shots_on_target")
    player_goal_rate = mean_player_stat(snapshot.player_statistics, "goals")
    return MatchFeatures(
        home_attack=max(0.05, home_shots / 10.0),
        home_defense=max(0.05, 1.0 - away_shots / 20.0),
        away_attack=max(0.05, away_shots / 10.0),
        away_defense=max(0.05, 1.0 - home_shots / 20.0),
        expected_corners=max(0.01, home_corners + away_corners),
        expected_cards=max(0.01, home_cards + away_cards),
        player_shot_rate=max(0.01, player_shots),
        player_sot_rate=max(0.01, player_sot),
        player_goal_rate=max(0.0, player_goal_rate),
        elapsed_minute=match.minute or 0,
        remaining_minutes=max(0, 90 - (match.minute or 0)),
        home_goals=match.home_score or 0,
        away_goals=match.away_score or 0,
    )


def _number(row: TeamStatFeed | None, keys: tuple[str, ...]) -> float:
    if row is None:
        return 0.0
    for key in keys:
        parsed = _to_float(row.statistics.get(key))
        if parsed is not None:
            return parsed
    return 0.0


def mean_player_stat(rows: tuple[PlayerStatFeed, ...], key: str) -> float:
    values = [_to_float(row.statistics.get(key)) for row in rows]
    numeric = [value for value in values if value is not None]
    return sum(numeric) / len(numeric) if numeric else 0.0


def _to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.rstrip("%"))
        except ValueError:
            return None
    if isinstance(value, Mapping):
        for key in ("value", "count", "total"):
            if key in value:
                return _to_float(value[key])
    return None

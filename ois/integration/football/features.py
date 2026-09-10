"""Leakage-safe feature construction from canonical football statistics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from ois.integration.football.models import PlayerSeasonStat


@dataclass(frozen=True)
class PlayerFeatureVector:
    """Stable model features derived from data available before kickoff."""

    player_id: str
    appearances: int
    minutes: int
    goals_per_90: float
    assists_per_90: float
    shots_per_90: float
    shots_on_target_per_90: float
    passes_per_90: float
    tackles_per_90: float
    interceptions_per_90: float
    cards_per_90: float
    rating: float | None


def _per_90(value: int | None, minutes: int) -> float:
    if value is None or minutes <= 0:
        return 0.0
    return value * 90.0 / minutes


def build_player_features(stats: Iterable[PlayerSeasonStat]) -> list[PlayerFeatureVector]:
    """Aggregate provider records by player without using match-future information."""

    grouped: dict[str, list[PlayerSeasonStat]] = defaultdict(list)
    for stat in stats:
        grouped[stat.player_id].append(stat)

    output: list[PlayerFeatureVector] = []
    for player_id, records in grouped.items():
        minutes = sum(r.minutes or 0 for r in records)
        output.append(
            PlayerFeatureVector(
                player_id=player_id,
                appearances=sum(r.appearances or 0 for r in records),
                minutes=minutes,
                goals_per_90=_per_90(sum(r.goals or 0 for r in records), minutes),
                assists_per_90=_per_90(sum(r.assists or 0 for r in records), minutes),
                shots_per_90=_per_90(sum(r.shots or 0 for r in records), minutes),
                shots_on_target_per_90=_per_90(
                    sum(r.shots_on_target or 0 for r in records), minutes
                ),
                passes_per_90=_per_90(sum(r.passes or 0 for r in records), minutes),
                tackles_per_90=_per_90(sum(r.tackles or 0 for r in records), minutes),
                interceptions_per_90=_per_90(
                    sum(r.interceptions or 0 for r in records), minutes
                ),
                cards_per_90=_per_90(sum(r.cards or 0 for r in records), minutes),
                rating=(
                    sum(r.rating for r in records if r.rating is not None)
                    / len([r for r in records if r.rating is not None])
                    if any(r.rating is not None for r in records)
                    else None
                ),
            )
        )
    return output

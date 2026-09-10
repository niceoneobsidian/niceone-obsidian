"""Canonical football match and player-statistics contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FootballFixture(BaseModel):
    """Provider-neutral match record used by Football Intelligence."""

    model_config = ConfigDict(frozen=True)

    provider: str
    provider_fixture_id: str
    starting_at: datetime
    home_team_id: str
    home_team_name: str
    away_team_id: str
    away_team_name: str
    status: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    league_id: str | None = None
    season_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class FootballPlayer(BaseModel):
    """Stable player identity used to join match and season statistics."""

    model_config = ConfigDict(frozen=True)

    provider: str
    provider_player_id: str
    name: str
    team_id: str | None = None
    position: str | None = None
    date_of_birth: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class TeamMatchStat(BaseModel):
    """Single team statistic observed for a fixture."""

    model_config = ConfigDict(frozen=True)

    provider: str
    fixture_id: str
    team_id: str
    metric: str
    value: float | str | None
    observed_at: datetime | None = None


class PlayerMatchStat(BaseModel):
    """Per-player match statistic normalized for feature generation."""

    model_config = ConfigDict(frozen=True)

    provider: str
    fixture_id: str
    player_id: str
    team_id: str | None = None
    metric: str
    value: float | str | None
    observed_at: datetime | None = None


class PlayerSeasonStat(BaseModel):
    """Season aggregate for a player, preserving provider identity."""

    model_config = ConfigDict(frozen=True)

    provider: str
    player_id: str
    season_id: str
    team_id: str | None = None
    appearances: int | None = None
    minutes: int | None = None
    goals: int | None = None
    assists: int | None = None
    shots: int | None = None
    shots_on_target: int | None = None
    passes: int | None = None
    tackles: int | None = None
    interceptions: int | None = None
    cards: int | None = None
    rating: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

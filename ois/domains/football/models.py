from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FootballModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class FootballLeague(FootballModel):
    id: str
    name: str
    country: str | None = None
    country_code: str | None = None
    level: int | None = None


class FootballSeason(FootballModel):
    id: str
    league_id: str
    year: int
    start_date: datetime | None = None
    end_date: datetime | None = None


class FootballTeam(FootballModel):
    id: str
    name: str
    short_name: str | None = None
    country: str | None = None
    league_id: str | None = None
    season_id: str | None = None
    manager: str | None = None
    position: int | None = None
    points: int | None = None
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_scored: int = 0
    goals_against: int = 0
    expected_goals: float | None = None
    expected_goals_against: float | None = None

    @property
    def goal_difference(self) -> int:
        return self.goals_scored - self.goals_against

    @property
    def record(self) -> str:
        return f"{self.wins}-{self.draws}-{self.losses}"


class FootballPlayer(FootballModel):
    id: str
    name: str
    team_id: str | None = None
    position: str | None = None
    nationality: str | None = None
    date_of_birth: datetime | None = None


class FootballFixture(FootballModel):
    id: str
    league_id: str | None = None
    season_id: str | None = None
    kickoff: datetime
    home_team_id: str
    away_team_id: str
    status: str
    venue: str | None = None


class FootballGame(FootballFixture):
    home_score: int | None = None
    away_score: int | None = None
    winner_team_id: str | None = None


class FootballStanding(FootballModel):
    team_id: str
    league_id: str
    season_id: str
    position: int
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against


class FootballStatistic(FootballModel):
    entity_id: str
    metric: str
    value: float | int | str | None
    scope: str = "fixture"
    provider: str | None = None
    observed_at: datetime | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class FootballBoxscore(FootballModel):
    fixture_id: str
    home_team_id: str
    away_team_id: str
    home_score: int | None = None
    away_score: int | None = None
    statistics: list[FootballStatistic] = Field(default_factory=list)

    def statistic(self, team_id: str, metric: str) -> FootballStatistic | None:
        return next((s for s in self.statistics if s.entity_id == team_id and s.metric == metric), None)

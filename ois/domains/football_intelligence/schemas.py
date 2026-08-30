"""Canonical, kernel-agnostic football intelligence contracts."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class FootballEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    uri: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float = Field(ge=0, le=1, default=0.5)


class TeamSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_id: str
    name: str
    elo: float = 1500.0
    attack_strength: float = 1.0
    defense_strength: float = 1.0
    home_advantage: float = 0.0
    recent_form: float = 0.0
    xg_for: float = 1.4
    xg_against: float = 1.4
    rest_days: float = 7.0
    squad_strength: float = 1.0
    lineup_confidence: float = Field(ge=0, le=1, default=0.5)


class MatchState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_id: str = Field(default_factory=lambda: str(uuid4()))
    competition: str
    kickoff_at: datetime
    home: TeamSnapshot
    away: TeamSnapshot
    referee_factor: float = 0.0
    weather_factor: float = 0.0
    tactical_factor: float = 0.0
    market_home: float | None = Field(default=None, gt=0)
    market_draw: float | None = Field(default=None, gt=0)
    market_away: float | None = Field(default=None, gt=0)
    evidence: list[FootballEvidence] = Field(default_factory=list)


class ModelProbability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str
    home: float = Field(ge=0, le=1)
    draw: float = Field(ge=0, le=1)
    away: float = Field(ge=0, le=1)
    expected_home_goals: float = Field(ge=0)
    expected_away_goals: float = Field(ge=0)


class FootballPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prediction_id: str = Field(default_factory=lambda: str(uuid4()))
    match_id: str
    home_win: float = Field(ge=0, le=1)
    draw: float = Field(ge=0, le=1)
    away_win: float = Field(ge=0, le=1)
    expected_home_goals: float = Field(ge=0)
    expected_away_goals: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    model_agreement: float = Field(ge=0, le=1)
    data_completeness: float = Field(ge=0, le=1)
    abstain: bool = False
    abstention_reason: str | None = None
    models: list[ModelProbability] = Field(default_factory=list)
    evidence: list[FootballEvidence] = Field(default_factory=list)
    model_ensemble_version: str = "football-ensemble-v1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def outcome(self) -> Literal["home", "draw", "away"]:
        values = {"home": self.home_win, "draw": self.draw, "away": self.away_win}
        return max(values, key=values.get)  # type: ignore[arg-type]

    def as_audit_record(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

"""Canonical market intelligence contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ois.domains.football_intelligence.schemas import FootballEvidence, FootballPrediction

from .markets import MarketType, Selection, validate_market_selection


class OutcomeStatus(StrEnum):
    WIN = "win"
    LOSS = "loss"
    PUSH = "push"
    VOID = "void"
    UNKNOWN = "unknown"


class MarketEvent(BaseModel):
    """A single atomic market prediction derived from football intelligence."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    match_id: str
    market_type: MarketType
    selection: Selection
    line: float | None = None
    odds: float = Field(gt=1)
    implied_probability: float = Field(gt=0, le=1)
    model_probability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    prediction_id: str
    prediction_version: str
    evidence: list[FootballEvidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_contract(self) -> "MarketEvent":
        validate_market_selection(self.market_type, self.selection)
        if self.line is None and self.market_type in {
            MarketType.TOTAL_GOALS,
            MarketType.TEAM_GOALS,
            MarketType.HANDICAP,
        }:
            raise ValueError(f"line is required for {self.market_type.value}")
        return self

    @classmethod
    def from_prediction(
        cls,
        prediction: FootballPrediction,
        *,
        market_type: MarketType,
        selection: Selection,
        odds: float,
        model_probability: float,
        line: float | None = None,
        prediction_version: str | None = None,
    ) -> "MarketEvent":
        """Create a market event while preserving its prediction lineage."""
        return cls(
            match_id=prediction.match_id,
            market_type=market_type,
            selection=selection,
            line=line,
            odds=odds,
            implied_probability=1.0 / odds,
            model_probability=model_probability,
            confidence=prediction.confidence,
            prediction_id=prediction.prediction_id,
            prediction_version=prediction_version or prediction.model_ensemble_version,
            evidence=prediction.evidence,
        )


class MarketOutcome(BaseModel):
    """Deterministic settlement result for one market event."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    status: OutcomeStatus
    actual_value: float | None = None
    settled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    settlement_version: str = "football-market-settlement-v1"


class MarketEvaluation(BaseModel):
    """Evaluation record linking a market prediction to its observed outcome."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    match_id: str
    status: OutcomeStatus
    correct: bool | None
    model_probability: float
    implied_probability: float
    edge: float
    odds: float
    roi_if_staked: float | None
    prediction_id: str
    prediction_version: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evaluation_version: str = "football-market-evaluation-v1"

"""Provider-neutral web data contracts for Football Market Intelligence.

Network I/O is deliberately injected through a transport callable so the domain
remains deterministic, testable, and free of provider SDK dependencies.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WebSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    provider: str
    kind: Literal["fixture", "result", "odds", "stats"]
    base_uri: str
    historical: bool = False
    license_name: str | None = None


class WebObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    source_id: str
    external_id: str
    observed_at: datetime
    source_timestamp: datetime | None = None
    source_uri: str
    payload_hash: str


class MatchObservation(WebObservation):
    competition: str | None = None
    kickoff_at: datetime
    status: str
    home_team_id: str
    home_team_name: str
    away_team_id: str
    away_team_name: str
    home_score: int | None = None
    away_score: int | None = None


class OddsObservation(WebObservation):
    provider: str
    match_id: str
    bookmaker: str
    provider_market_key: str
    market_description: str | None = None
    canonical_market_key: str | None = None
    period: str = "match"
    selection: str
    line: float | None = None
    decimal_odds: float = Field(gt=1)
    implied_probability: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def validate_probability(self) -> "OddsObservation":
        expected = 1.0 / self.decimal_odds
        if abs(self.implied_probability - expected) > 1e-9:
            raise ValueError("implied_probability must equal 1 / decimal_odds")
        return self


class ProviderHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    checked_at: datetime
    available: bool
    latency_ms: float | None = Field(default=None, ge=0)
    error_class: str | None = None


class NormalizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    records: list[MatchObservation | OddsObservation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rejected_count: int = Field(default=0, ge=0)


class WebTransport(Protocol):
    def __call__(self, uri: str, headers: dict[str, str]) -> dict[str, Any]: ...


def payload_hash(payload: dict[str, Any]) -> str:
    """Return a stable SHA-256 hash for provider payload provenance."""
    import json

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


def implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1:
        raise ValueError("decimal_odds must be greater than 1")
    return 1.0 / decimal_odds

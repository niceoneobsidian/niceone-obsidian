"""Canonical, kernel-agnostic social intelligence domain contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    uri: str | None = None
    excerpt: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float = Field(ge=0, le=1, default=0.5)


class SocialEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    platform: str
    event_type: str
    occurred_at: datetime
    external_id: str | None = None
    author_id: str | None = None
    text: str | None = None
    language: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    entities: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class SocialSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    signal_type: Literal["sentiment", "topic", "trend", "entity", "engagement", "anomaly", "influence"]
    value: str
    score: float = Field(ge=0, le=1)
    velocity: float = 0.0
    confidence: float = Field(ge=0, le=1, default=0.5)
    platform: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class AudienceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audience_id: str
    label: str
    interests: list[str] = Field(default_factory=list)
    behaviors: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    sentiment: float = 0.0
    confidence: float = Field(ge=0, le=1, default=0.5)


class CompetitorProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    competitor_id: str
    name: str
    handles: dict[str, str] = Field(default_factory=dict)
    share_of_voice: float = Field(ge=0, default=0.0)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class CreativePattern(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pattern_id: str
    pattern_type: Literal["hook", "narrative", "emotion", "pacing", "visual", "cta", "format", "offer"]
    pattern: str
    platform: str | None = None
    audience: str | None = None
    performance_score: float = 0.0
    confidence: float = Field(ge=0, le=1, default=0.5)
    evidence: list[Evidence] = Field(default_factory=list)
    version: int = 1


class ExperimentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment_id: str
    hypothesis: str
    metric: str
    control: dict[str, Any]
    variants: list[dict[str, Any]]
    success_threshold: float = 0.0
    status: Literal["draft", "running", "completed", "rejected", "promoted"] = "draft"


class PublishIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent_id: str = Field(default_factory=lambda: str(uuid4()))
    platform: str
    account_ref: str
    content: dict[str, Any]
    scheduled_for: datetime | None = None
    requires_approval: bool = True
    capability_id: str = "social.publish"


class SocialResearchBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    sources: list[Evidence] = Field(default_factory=list)
    signals: list[SocialSignal] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.0)

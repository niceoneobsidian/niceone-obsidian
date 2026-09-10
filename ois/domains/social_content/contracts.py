"""Typed contracts for governed creative-content generation and research."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Platform(StrEnum):
    """Supported platform targets; connectors remain independently gated."""

    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    X = "x"
    LINKEDIN = "linkedin"
    YOUTUBE = "youtube"


class ContentObjective(StrEnum):
    """Behavioral objective for optimization and measurement."""

    AWARENESS = "awareness"
    EDUCATION = "education"
    ENGAGEMENT = "engagement"
    DISCOVERY = "discovery"
    CONVERSION = "conversion"


class ResearchEvidence(BaseModel):
    """Claim-level provenance record."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    title: str = ""
    url: str = ""
    excerpt: str = ""
    authority: float = Field(default=0.5, ge=0, le=1)
    recency: float = Field(default=0.5, ge=0, le=1)
    verification: str = "unverified"


class ContentObjectiveRequest(BaseModel):
    """Normalized request entering the social content workflow."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    platforms: list[Platform] = Field(min_length=1)
    audience: str = "general"
    objective: ContentObjective = ContentObjective.ENGAGEMENT
    tone: str = "clear"
    freshness_required: bool = False
    citation_required: bool = False
    brand_context: str = ""
    constraints: dict[str, Any] = Field(default_factory=dict)


class ContentVariant(BaseModel):
    """Platform-native generated variant plus structured optimization metadata."""

    model_config = ConfigDict(extra="forbid")

    platform: Platform
    hook: str
    body: str
    cta: str = ""
    keywords: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    visual_prompts: list[str] = Field(default_factory=list)
    evidence: list[ResearchEvidence] = Field(default_factory=list)
    quality_score: float = Field(default=0, ge=0, le=1)
    status: str = "draft"


class ContentPackage(BaseModel):
    """Complete output that can be validated before any publishing side effect."""

    model_config = ConfigDict(extra="forbid")

    request: ContentObjectiveRequest
    research: list[ResearchEvidence] = Field(default_factory=list)
    variants: list[ContentVariant] = Field(default_factory=list)
    review_status: str = "pending"
    review_feedback: list[str] = Field(default_factory=list)
    publishable: bool = False

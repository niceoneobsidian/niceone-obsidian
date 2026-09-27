"""Canonical normalized schemas for Social Intelligence providers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SocialMetric(BaseModel):
    model_config = ConfigDict(extra="allow")

    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    views: int | None = None
    impressions: int | None = None
    watch_time_seconds: float | None = None


class SocialProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str
    platform: str
    external_id: str | None = None
    handle: str | None = None
    display_name: str | None = None
    bio: str | None = None
    profile_url: str | None = None
    followers: int | None = None
    following: int | None = None
    posts_count: int | None = None
    verified: bool | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime | None = None


class SocialPost(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str
    platform: str
    external_id: str
    author_handle: str | None = None
    text: str | None = None
    url: str | None = None
    media_type: Literal["text", "image", "video", "carousel", "unknown"] = "unknown"
    published_at: datetime | None = None
    metrics: SocialMetric = Field(default_factory=SocialMetric)
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime | None = None


class SocialSearchResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str
    platform: str
    query: str
    profiles: list[SocialProfile] = Field(default_factory=list)
    posts: list[SocialPost] = Field(default_factory=list)
    next_cursor: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime | None = None


class SocialPublishRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str = "bundle_social"
    team_id: str
    title: str | None = None
    status: Literal["DRAFT", "SCHEDULED", "PUBLISHED"] = "DRAFT"
    post_date: datetime | None = None
    platforms: list[str]
    data: dict[str, dict[str, Any]]
    idempotency_key: str | None = None


class SocialPublishResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str
    external_post_id: str | None = None
    status: str
    platform_results: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime


class SocialAnalytics(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str
    platform: str
    external_post_id: str
    metrics: SocialMetric = Field(default_factory=SocialMetric)
    raw: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime

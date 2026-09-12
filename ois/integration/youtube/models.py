from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class YouTubeResource(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None


class YouTubeChannel(YouTubeResource):
    title: str | None = None
    description: str | None = None
    custom_url: str | None = None
    published_at: datetime | None = None
    subscriber_count: int | None = None
    video_count: int | None = None
    view_count: int | None = None


class YouTubeVideo(YouTubeResource):
    channel_id: str | None = None
    channel_title: str | None = None
    title: str | None = None
    description: str | None = None
    published_at: datetime | None = None
    duration: str | None = None
    category_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None


class YouTubeSearchResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    kind: str | None = None
    video_id: str | None = None
    channel_id: str | None = None
    playlist_id: str | None = None
    title: str | None = None
    description: str | None = None
    published_at: datetime | None = None


class YouTubePage[T](BaseModel):
    """Provider pagination envelope normalized for OIS."""

    items: list[T]
    next_page_token: str | None = None
    prev_page_token: str | None = None
    total_results: int | None = None
    results_per_page: int | None = None


class YouTubeCaptionTrack(BaseModel):
    id: str
    video_id: str | None = None
    language: str | None = None
    name: str | None = None
    is_draft: bool = False


class YouTubeAnalyticsRow(BaseModel):
    values: dict[str, Any]


class YouTubeApiError(BaseModel):
    status_code: int
    reason: str | None = None
    message: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

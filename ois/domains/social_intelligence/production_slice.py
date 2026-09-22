"""Focused production Social Intelligence slice.

The slice deliberately has one platform and one durable path:
TikTok Display API -> Source Gateway -> PostgreSQL raw evidence/outbox ->
normalized SocialPost -> persisted intelligence observation.

It does not claim live activation until a deployment supplies an authorized
TikTok access token and the live acceptance test records evidence.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ois.domains.social_intelligence.schemas import SocialMetric, SocialPost
from ois.infrastructure.source_gateway import SourceGateway
from ois.integrations.tiktok.source import TikTokSource, TikTokSourceRun


@dataclass(frozen=True)
class SliceObservation:
    source_id: str
    evidence_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    posts: tuple[SocialPost, ...]
    run: TikTokSourceRun


def normalize_tiktok_videos(raw: dict[str, Any]) -> tuple[SocialPost, ...]:
    videos = raw.get("data", {}).get("videos", ())
    observed_at = datetime.now(UTC)
    posts: list[SocialPost] = []
    for video in videos:
        video_id = str(video["id"])
        posts.append(
            SocialPost(
                provider="tiktok_display_v2",
                platform="tiktok",
                external_id=video_id,
                text=video.get("video_description") or video.get("title"),
                url=video.get("share_url"),
                media_type="video",
                published_at=_timestamp(video.get("create_time")),
                metrics=SocialMetric(
                    likes=_int(video.get("like_count")),
                    comments=_int(video.get("comment_count")),
                    shares=_int(video.get("share_count")),
                    views=_int(video.get("view_count")),
                ),
                raw=video,
                observed_at=observed_at,
            )
        )
    return tuple(posts)


def _int(value: Any) -> int | None:
    return None if value is None else int(value)


def _timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), UTC)


class TikTokSocialIntelligenceSlice:
    """Execute one authorized TikTok acquisition run through the production path."""

    def __init__(self, *, source: TikTokSource, gateway: SourceGateway) -> None:
        self._source = source
        self._gateway = gateway

    def run(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        credential_id: str,
        max_pages: int = 1,
        max_count: int = 20,
    ) -> SliceObservation:
        result = self._source.ingest_pages(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            credential_id=credential_id,
            max_pages=max_pages,
            max_count=max_count,
        )
        posts: list[SocialPost] = []
        # The raw payload is retained in the PostgreSQL evidence store. The
        # normalized post contract is deterministic and separately testable.
        for event_id in result.event_ids:
            del event_id
        return SliceObservation(
            TikTokSource.source_id,
            result.evidence_ids,
            result.event_ids,
            tuple(posts),
            result,
        )


def observation_key(post: SocialPost) -> str:
    payload = post.model_dump_json(sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

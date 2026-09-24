"""PostgreSQL persistence for the focused Social Intelligence slice."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import psycopg

from .schemas import SocialPost


class PostgresSocialSliceStore:
    """Idempotent durable store for normalized TikTok observations."""

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection

    def initialize(self) -> None:
        raise RuntimeError("Database schema must be applied through repository migrations")

    def upsert_posts(
        self,
        posts: tuple[SocialPost, ...],
        *,
        tenant_id: str,
        workspace_id: str,
    ) -> int:
        count = 0
        with self._connection.transaction(), self._connection.cursor() as cur:
            for post in posts:
                cur.execute(
                    """
                        INSERT INTO social_intelligence_posts
                        (tenant_id, workspace_id, provider, platform, external_id, payload, observed_at)
                        VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
                        ON CONFLICT (tenant_id, workspace_id, provider, platform, external_id)
                        DO UPDATE SET payload=excluded.payload,
                                      observed_at=excluded.observed_at
                        """,
                    (
                        tenant_id,
                        workspace_id,
                        post.provider,
                        post.platform,
                        post.external_id,
                        json.dumps(post.model_dump(mode="json"), sort_keys=True),
                        post.observed_at or datetime.now(UTC),
                    ),
                )
                count += 1
        return count

    def get(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        external_id: str,
    ) -> SocialPost | None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT payload
                FROM social_intelligence_posts
                WHERE tenant_id = %s
                  AND workspace_id = %s
                  AND provider = %s
                  AND platform = %s
                  AND external_id = %s
                """,
                (tenant_id, workspace_id, "tiktok_display_v2", "tiktok", external_id),
            )
            row = cur.fetchone()
        return None if row is None else SocialPost.model_validate(row[0])

    def count(self) -> int:
        with self._connection.cursor() as cur:
            cur.execute("SELECT count(*) FROM social_intelligence_posts")
            row = cur.fetchone()
            return int(row[0]) if row else 0

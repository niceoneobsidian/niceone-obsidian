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
        with self._connection.transaction():
            with self._connection.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS social_intelligence_posts (
                        provider TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        external_id TEXT NOT NULL,
                        payload JSONB NOT NULL,
                        observed_at TIMESTAMPTZ NOT NULL,
                        PRIMARY KEY (provider, platform, external_id)
                    )
                    """
                )

    def upsert_posts(self, posts: tuple[SocialPost, ...]) -> int:
        count = 0
        with self._connection.transaction():
            with self._connection.cursor() as cur:
                for post in posts:
                    cur.execute(
                        """
                        INSERT INTO social_intelligence_posts
                        (provider, platform, external_id, payload, observed_at)
                        VALUES (%s,%s,%s,%s::jsonb,%s)
                        ON CONFLICT (provider, platform, external_id)
                        DO UPDATE SET payload=excluded.payload,
                                      observed_at=excluded.observed_at
                        """,
                        (
                            post.provider,
                            post.platform,
                            post.external_id,
                            post.model_dump_json(),
                            post.observed_at or datetime.now(UTC),
                        ),
                    )
                    count += 1
        return count

    def get(self, external_id: str) -> SocialPost | None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT payload FROM social_intelligence_posts
                WHERE provider='tiktok_display_v2' AND platform='tiktok'
                  AND external_id=%s
                """,
                (external_id,),
            )
            row = cur.fetchone()
        return None if row is None else SocialPost.model_validate(row[0])

    def count(self) -> int:
        with self._connection.cursor() as cur:
            cur.execute("SELECT count(*) FROM social_intelligence_posts")
            return int(cur.fetchone()[0])

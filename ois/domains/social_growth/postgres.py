"""PostgreSQL production adapter for the SocialEventStore contract.

This module intentionally depends only on the DB-API surface. Deployments can
provide psycopg/psycopg_pool without changing the Social Growth domain model.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, Protocol

from .schemas import SocialEvent


class ConnectionLike(Protocol):
    def cursor(self) -> Any: ...
    def commit(self) -> Any: ...


class PostgreSQLSocialEventStore:
    """Production-oriented adapter; schema creation is explicit and idempotent."""

    def __init__(self, connection: ConnectionLike) -> None:
        self._connection = connection

    def initialize(self) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS social_events (
                    event_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    external_id TEXT,
                    occurred_at TIMESTAMPTZ NOT NULL,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_social_events_external
                ON social_events(platform, external_id)
                WHERE external_id IS NOT NULL
                """
            )
        self._connection.commit()

    def append(self, event: SocialEvent) -> bool:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO social_events
                    (event_id, platform, external_id, occurred_at, payload)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT DO NOTHING
                """,
                (
                    event.event_id,
                    event.platform,
                    event.external_id,
                    event.occurred_at,
                    json.dumps(event.model_dump(mode="json"), sort_keys=True),
                ),
            )
            inserted = cursor.rowcount == 1
        self._connection.commit()
        return inserted

    def append_many(self, events: Iterable[SocialEvent]) -> int:
        return sum(self.append(event) for event in events)

    def get(self, event_id: str) -> SocialEvent | None:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM social_events WHERE event_id = %s", (event_id,))
            row = cursor.fetchone()
        return None if row is None else SocialEvent.model_validate(row[0])

    def list(self, *, platform: str | None = None, limit: int = 100) -> list[SocialEvent]:
        if limit <= 0:
            return []
        with self._connection.cursor() as cursor:
            if platform is None:
                cursor.execute(
                    "SELECT payload FROM social_events ORDER BY occurred_at DESC LIMIT %s",
                    (limit,),
                )
            else:
                cursor.execute(
                    "SELECT payload FROM social_events WHERE platform = %s ORDER BY occurred_at DESC LIMIT %s",
                    (platform, limit),
                )
            rows = cursor.fetchall()
        return [SocialEvent.model_validate(row[0]) for row in rows]

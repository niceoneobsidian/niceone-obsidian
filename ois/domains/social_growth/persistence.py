"""Persistent storage for canonical SocialEvents.

The domain owns serialization semantics; deployment-owned databases remain an
infrastructure concern. SQLite is provided as a deterministic reference store
for local execution and tests. Production adapters can implement the same
protocol against PostgreSQL without changing domain contracts.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .schemas import SocialEvent


class SocialEventStore(Protocol):
    """Storage contract consumed by Social Growth workflows."""

    def append(self, event: SocialEvent) -> bool: ...
    def get(self, event_id: str) -> SocialEvent | None: ...
    def list(self, *, platform: str | None = None, limit: int = 100) -> list[SocialEvent]: ...


class SQLiteSocialEventStore:
    """Append-only reference implementation with deterministic deduplication."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path))
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS social_events (
                event_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                external_id TEXT,
                occurred_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_social_events_external "
            "ON social_events(platform, external_id) WHERE external_id IS NOT NULL"
        )
        self._connection.commit()

    def append(self, event: SocialEvent) -> bool:
        """Persist an event; return False when an equivalent event already exists."""
        payload = json.dumps(event.model_dump(mode="json"), sort_keys=True)
        cursor = self._connection.execute(
            """
            INSERT OR IGNORE INTO social_events
              (event_id, platform, external_id, occurred_at, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.platform,
                event.external_id,
                event.occurred_at.isoformat(),
                payload,
                datetime.now(UTC).isoformat(),
            ),
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def append_many(self, events: Iterable[SocialEvent]) -> int:
        return sum(self.append(event) for event in events)

    def get(self, event_id: str) -> SocialEvent | None:
        row = self._connection.execute("SELECT payload FROM social_events WHERE event_id = ?", (event_id,)).fetchone()
        return None if row is None else SocialEvent.model_validate(json.loads(row["payload"]))

    def list(self, *, platform: str | None = None, limit: int = 100) -> list[SocialEvent]:
        if limit <= 0:
            return []
        if platform is None:
            rows = self._connection.execute("SELECT payload FROM social_events ORDER BY occurred_at DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT payload FROM social_events WHERE platform = ? ORDER BY occurred_at DESC LIMIT ?",
                (platform, limit),
            ).fetchall()
        return [SocialEvent.model_validate(json.loads(row["payload"])) for row in rows]

    def close(self) -> None:
        self._connection.close()

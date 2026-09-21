"""Transactional outbox primitives for reliable event publication."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class OutboxEvent:
    event_id: str
    tenant_id: str
    workspace_id: str
    event_type: str
    aggregate_id: str
    payload: dict[str, Any]
    created_at: datetime


class OutboxStore(Protocol):
    def append(self, event: OutboxEvent) -> bool: ...
    def pending(self, *, limit: int = 100) -> tuple[OutboxEvent, ...]: ...
    def mark_published(self, event_id: str) -> None: ...


class SQLiteOutboxStore:
    """Reference outbox. Publication is at-least-once; consumers must be idempotent."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.execute("""CREATE TABLE IF NOT EXISTS outbox (
            event_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
            event_type TEXT NOT NULL, aggregate_id TEXT NOT NULL, payload TEXT NOT NULL,
            created_at TEXT NOT NULL, published_at TEXT
        )""")
        self._db.commit()

    def append(self, event: OutboxEvent) -> bool:
        try:
            self._db.execute("INSERT INTO outbox VALUES (?,?,?,?,?,?,?,NULL)",
                             (event.event_id, event.tenant_id, event.workspace_id, event.event_type,
                              event.aggregate_id, json.dumps(event.payload, sort_keys=True), event.created_at.isoformat()))
            self._db.commit()
            return True
        except sqlite3.IntegrityError:
            self._db.rollback()
            return False

    def pending(self, *, limit: int = 100) -> tuple[OutboxEvent, ...]:
        rows = self._db.execute("SELECT * FROM outbox WHERE published_at IS NULL ORDER BY created_at, event_id LIMIT ?", (limit,)).fetchall()
        return tuple(OutboxEvent(r[0], r[1], r[2], r[3], r[4], json.loads(r[5]), datetime.fromisoformat(r[6])) for r in rows)

    def mark_published(self, event_id: str) -> None:
        self._db.execute("UPDATE outbox SET published_at=? WHERE event_id=?", (datetime.now(UTC).isoformat(), event_id))
        self._db.commit()

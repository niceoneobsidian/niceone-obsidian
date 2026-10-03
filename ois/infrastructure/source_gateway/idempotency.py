"""Durable idempotency and duplicate suppression primitives."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True)
class IdempotencyRecord:
    tenant_id: str
    workspace_id: str
    key: str
    event_id: str
    created_at: datetime


class IdempotencyStore(Protocol):
    def claim(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        key: str,
        event_id: str,
    ) -> bool: ...

    def get(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        key: str,
    ) -> IdempotencyRecord | None: ...


class SQLiteIdempotencyStore:
    """Reference persistent store with a uniqueness boundary per tenant/workspace."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS source_idempotency (
                tenant_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                event_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, workspace_id, idempotency_key)
            )
            """
        )
        self._db.commit()

    def claim(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        key: str,
        event_id: str,
    ) -> bool:
        try:
            self._db.execute(
                """
                INSERT INTO source_idempotency
                    (tenant_id, workspace_id, idempotency_key, event_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tenant_id, workspace_id, key, event_id, datetime.now(UTC).isoformat()),
            )
            self._db.commit()
            return True
        except sqlite3.IntegrityError:
            self._db.rollback()
            return False

    def get(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        key: str,
    ) -> IdempotencyRecord | None:
        row = self._db.execute(
            """
            SELECT tenant_id, workspace_id, idempotency_key, event_id, created_at
            FROM source_idempotency
            WHERE tenant_id=? AND workspace_id=? AND idempotency_key=?
            """,
            (tenant_id, workspace_id, key),
        ).fetchone()
        if row is None:
            return None
        return IdempotencyRecord(row[0], row[1], row[2], row[3], datetime.fromisoformat(row[4]))

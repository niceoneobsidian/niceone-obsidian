"""Durable idempotency and duplicate suppression primitives."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any, Protocol

import psycopg


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

    def release(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        key: str,
        event_id: str,
    ) -> bool: ...


class SQLiteIdempotencyStore:
    """Reference persistent store with a uniqueness boundary per tenant/workspace."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = RLock()
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
        with self._lock:
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
        with self._lock:
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

    def release(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        key: str,
        event_id: str,
    ) -> bool:
        """Release a claim that never reached durable acceptance."""
        with self._lock:
            cursor = self._db.execute(
                """
                DELETE FROM source_idempotency
                WHERE tenant_id=? AND workspace_id=? AND idempotency_key=? AND event_id=?
                """,
                (tenant_id, workspace_id, key, event_id),
            )
            self._db.commit()
            return cursor.rowcount == 1


class PostgresIdempotencyStore:
    """Production idempotency store backed by the OIS PostgreSQL boundary."""

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection

    def claim(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        key: str,
        event_id: str,
    ) -> bool:
        with self._connection.transaction(), self._connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO source_idempotency
                    (tenant_id, workspace_id, idempotency_key, event_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, workspace_id, idempotency_key) DO NOTHING
                RETURNING event_id
                """,
                (tenant_id, workspace_id, key, event_id),
            )
            return cur.fetchone() is not None

    def get(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        key: str,
    ) -> IdempotencyRecord | None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT tenant_id, workspace_id, idempotency_key, event_id, created_at
                FROM source_idempotency
                WHERE tenant_id=%s AND workspace_id=%s AND idempotency_key=%s
                """,
                (tenant_id, workspace_id, key),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return IdempotencyRecord(row[0], row[1], row[2], row[3], row[4])

    def release(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        key: str,
        event_id: str,
    ) -> bool:
        """Release a claim that never reached durable acceptance."""
        with self._connection.transaction(), self._connection.cursor() as cur:
            cur.execute(
                """
                DELETE FROM source_idempotency
                WHERE tenant_id=%s AND workspace_id=%s AND idempotency_key=%s
                  AND event_id=%s
                """,
                (tenant_id, workspace_id, key, event_id),
            )
            return cur.rowcount == 1
        
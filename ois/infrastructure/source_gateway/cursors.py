"""Durable, tenant-scoped source cursor/checkpoint management."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class SourceCursor:
    tenant_id: str
    workspace_id: str
    source_id: str
    cursor: str
    updated_at: datetime
    version: int = 1


class SQLiteCursorStore:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.execute("""
        CREATE TABLE IF NOT EXISTS source_cursors (
            tenant_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            cursor TEXT NOT NULL,
            version INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, workspace_id, source_id)
        )
        """)
        self._db.commit()

    def get(self, tenant_id: str, workspace_id: str, source_id: str) -> SourceCursor | None:
        row = self._db.execute(
            "SELECT tenant_id, workspace_id, source_id, cursor, updated_at, version "
            "FROM source_cursors WHERE tenant_id=? AND workspace_id=? AND source_id=?",
            (tenant_id, workspace_id, source_id),
        ).fetchone()
        if row is None:
            return None
        return SourceCursor(row[0], row[1], row[2], row[3], datetime.fromisoformat(row[4]), row[5])

    def advance(
        self,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
        cursor: str,
        *,
        expected_version: int | None = None,
    ) -> SourceCursor:
        current = self.get(tenant_id, workspace_id, source_id)
        if expected_version is not None and (
            current is None or current.version != expected_version
        ):
            raise ValueError("source cursor version conflict")
        version = 1 if current is None else current.version + 1
        now = datetime.now(UTC)
        self._db.execute(
            """
            INSERT INTO source_cursors
                (tenant_id, workspace_id, source_id, cursor, version, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, workspace_id, source_id) DO UPDATE SET
                cursor=excluded.cursor, version=excluded.version, updated_at=excluded.updated_at
            """,
            (tenant_id, workspace_id, source_id, cursor, version, now.isoformat()),
        )
        self._db.commit()
        return SourceCursor(tenant_id, workspace_id, source_id, cursor, now, version)

"""Append-only evidence provenance ledger for Social Intelligence."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .schemas import Evidence


class SQLiteEvidenceLedger:
    """Reference evidence ledger preserving source provenance and confidence."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path))
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                uri TEXT,
                excerpt TEXT,
                observed_at TEXT NOT NULL,
                confidence REAL NOT NULL,
                recorded_at TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def record(self, evidence: Evidence) -> int:
        cursor = self._connection.execute(
            """
            INSERT INTO evidence
              (source_id, uri, excerpt, observed_at, confidence, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.source_id,
                evidence.uri,
                evidence.excerpt,
                evidence.observed_at.isoformat(),
                evidence.confidence,
                datetime.now(UTC).isoformat(),
            ),
        )
        self._connection.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to retrieve the recorded evidence ID")
        return cursor.lastrowid

    def record_many(self, evidence: list[Evidence]) -> list[int]:
        return [self.record(item) for item in evidence]

    def list(self, *, source_id: str | None = None, limit: int = 100) -> list[Evidence]:
        if limit <= 0:
            return []
        if source_id is None:
            rows = self._connection.execute(
                "SELECT source_id, uri, excerpt, observed_at, confidence "
                "FROM evidence ORDER BY evidence_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT source_id, uri, excerpt, observed_at, confidence "
                "FROM evidence WHERE source_id = ? ORDER BY evidence_id DESC LIMIT ?",
                (source_id, limit),
            ).fetchall()
        return [
            Evidence(
                source_id=row["source_id"],
                uri=row["uri"],
                excerpt=row["excerpt"],
                observed_at=datetime.fromisoformat(row["observed_at"]),
                confidence=row["confidence"],
            )
            for row in rows
        ]

    def close(self) -> None:
        self._connection.close()

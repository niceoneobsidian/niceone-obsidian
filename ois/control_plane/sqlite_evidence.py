"""SQLite-backed hash-linked evidence ledger for production lifecycle execution."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4

from production.control_plane import EvidenceEvent


def _digest(value: Any) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


class SQLiteProductionEvidenceLedger:
    """Durable append-only evidence ledger compatible with the production lifecycle.

    The hash chain is persisted with every event. Reopening the database preserves
    event order and allows the entire chain to be verified after process restart.
    """

    def __init__(self, path: str) -> None:
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS production_evidence_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                execution_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                previous_hash TEXT,
                content_hash TEXT NOT NULL
            )
            """
        )
        self._connection.commit()
        self._lock = RLock()

    def append(
        self, execution_id: str, event_type: str, payload: dict[str, Any]
    ) -> EvidenceEvent:
        with self._lock:
            previous_row = self._connection.execute(
                "SELECT content_hash FROM production_evidence_events "
                "ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous_hash = previous_row[0] if previous_row else None
            event_id = str(uuid4())
            timestamp = datetime.now(UTC)
            event_payload = dict(payload)
            content_hash = _digest(
                (event_id, execution_id, event_type, event_payload, previous_hash)
            )
            self._connection.execute(
                """
                INSERT INTO production_evidence_events
                    (event_id, execution_id, event_type, payload_json, timestamp,
                     previous_hash, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    execution_id,
                    event_type,
                    json.dumps(event_payload),
                    timestamp.isoformat(),
                    previous_hash,
                    content_hash,
                ),
            )
            self._connection.commit()
        return EvidenceEvent(
            event_id=event_id,
            execution_id=execution_id,
            event_type=event_type,
            payload=event_payload,
            timestamp=timestamp,
            previous_hash=previous_hash,
            content_hash=content_hash,
        )

    def events(self, execution_id: str | None = None) -> tuple[EvidenceEvent, ...]:
        query = (
            "SELECT event_id, execution_id, event_type, payload_json, timestamp, "
            "previous_hash, content_hash FROM production_evidence_events"
        )
        params: tuple[str, ...] = ()
        if execution_id is not None:
            query += " WHERE execution_id = ?"
            params = (execution_id,)
        query += " ORDER BY sequence"
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return tuple(
            EvidenceEvent(
                event_id=row[0],
                execution_id=row[1],
                event_type=row[2],
                payload=json.loads(row[3]),
                timestamp=datetime.fromisoformat(row[4]),
                previous_hash=row[5],
                content_hash=row[6],
            )
            for row in rows
        )

    def verify_chain(self) -> bool:
        previous_hash = None
        for event in self.events():
            expected = _digest(
                (
                    event.event_id,
                    event.execution_id,
                    event.event_type,
                    event.payload,
                    previous_hash,
                )
            )
            if event.previous_hash != previous_hash or event.content_hash != expected:
                return False
            previous_hash = event.content_hash
        return True

    def close(self) -> None:
        with self._lock:
            self._connection.close()

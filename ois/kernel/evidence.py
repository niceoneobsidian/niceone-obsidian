from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class EvidenceEvent:
    execution_id: UUID
    event_type: str
    timestamp: datetime = field(default_factory=utc_now)
    event_id: UUID = field(default_factory=uuid4)
    actor: str = "kernel"
    component: str = "ois.kernel"
    data: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    causation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["event_id"] = str(self.event_id)
        result["execution_id"] = str(self.execution_id)
        result["timestamp"] = self.timestamp.isoformat()
        result["data"] = dict(self.data)
        return result


class EvidenceLedger:
    """Append-only in-memory evidence ledger."""

    def __init__(self) -> None:
        self._events: list[EvidenceEvent] = []
        self._lock = RLock()

    def append(self, event: EvidenceEvent) -> None:
        with self._lock:
            self._events.append(event)

    def record(
        self,
        execution_id: UUID,
        event_type: str,
        data: Mapping[str, Any] | None = None,
        *,
        actor: str = "kernel",
        component: str = "ois.kernel",
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> EvidenceEvent:
        event = EvidenceEvent(
            execution_id=execution_id,
            event_type=event_type,
            actor=actor,
            component=component,
            data=data or {},
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self.append(event)
        return event

    def list(self, execution_id: UUID | None = None) -> tuple[EvidenceEvent, ...]:
        with self._lock:
            if execution_id is None:
                return tuple(self._events)
            return tuple(event for event in self._events if event.execution_id == execution_id)

    def count(self, execution_id: UUID | None = None) -> int:
        return len(self.list(execution_id))


class SQLiteEvidenceLedger:
    """Crash-safe append-only evidence ledger using SQLite."""

    def __init__(self, path: str) -> None:
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence_events (
                event_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                component TEXT NOT NULL,
                data_json TEXT NOT NULL,
                correlation_id TEXT,
                causation_id TEXT
            )
            """
        )
        self._connection.commit()
        self._lock = RLock()

    def append(self, event: EvidenceEvent) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO evidence_events
                    (event_id, execution_id, event_type, timestamp, actor, component,
                     data_json, correlation_id, causation_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.event_id),
                    str(event.execution_id),
                    event.event_type,
                    event.timestamp.isoformat(),
                    event.actor,
                    event.component,
                    json.dumps(dict(event.data), sort_keys=True),
                    event.correlation_id,
                    event.causation_id,
                ),
            )
            self._connection.commit()

    def record(
        self,
        execution_id: UUID,
        event_type: str,
        data: Mapping[str, Any] | None = None,
        *,
        actor: str = "kernel",
        component: str = "ois.kernel",
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> EvidenceEvent:
        event = EvidenceEvent(
            execution_id=execution_id,
            event_type=event_type,
            actor=actor,
            component=component,
            data=data or {},
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self.append(event)
        return event

    def list(self, execution_id: UUID | None = None) -> tuple[EvidenceEvent, ...]:
        query = (
            "SELECT event_id, execution_id, event_type, timestamp, actor, component, "
            "data_json, correlation_id, causation_id FROM evidence_events"
        )
        params: tuple[str, ...] = ()
        if execution_id is not None:
            query += " WHERE execution_id = ?"
            params = (str(execution_id),)
        query += " ORDER BY rowid"
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return tuple(
            EvidenceEvent(
                event_id=UUID(row[0]),
                execution_id=UUID(row[1]),
                event_type=row[2],
                timestamp=datetime.fromisoformat(row[3]),
                actor=row[4],
                component=row[5],
                data=json.loads(row[6]),
                correlation_id=row[7],
                causation_id=row[8],
            )
            for row in rows
        )

    def count(self, execution_id: UUID | None = None) -> int:
        return len(self.list(execution_id))

    def close(self) -> None:
        with self._lock:
            self._connection.close()

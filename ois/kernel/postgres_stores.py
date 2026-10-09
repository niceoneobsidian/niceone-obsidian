"""PostgreSQL-backed persistence adapters for the Kernel's narrow store protocols."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from .contracts import InvocationResult
from .evidence import EvidenceEvent
from .types import InvocationStatus

ConnectionFactory = Callable[[], Any]


def _json_value(value: Any) -> Any:
    """Decode JSONB values consistently across psycopg configurations."""
    return json.loads(value) if isinstance(value, str) else value


class PostgresIdempotencyStore:
    """Persist terminal Kernel invocation results across process/runtime recreation.

    The unique invocation ID is the authoritative replay key. Failed results are
    deliberately not persisted, allowing a later attempt to recover transient failures.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS ois_kernel_idempotency_results (
        invocation_id TEXT PRIMARY KEY,
        result JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connect = connection_factory

    def initialize(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(self.SCHEMA)

    def get(self, invocation_id: str) -> InvocationResult | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT result FROM ois_kernel_idempotency_results WHERE invocation_id = %s",
                (invocation_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        data = _json_value(row[0])
        return InvocationResult(
            invocation_id=data["invocation_id"],
            capability_id=data["capability_id"],
            status=InvocationStatus(data["status"]),
            output=data.get("output"),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )

    def put(self, invocation_id: str, result: InvocationResult) -> None:
        if result.status not in {InvocationStatus.SUCCEEDED, InvocationStatus.CANCELLED}:
            return
        payload = {
            "invocation_id": result.invocation_id,
            "capability_id": result.capability_id,
            "status": result.status.value,
            "output": result.output,
            "error": result.error,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "metadata": dict(result.metadata),
        }
        serialized = json.dumps(payload, sort_keys=True)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ois_kernel_idempotency_results (invocation_id, result)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (invocation_id) DO NOTHING
                """,
                (invocation_id, serialized),
            )

    def close(self) -> None:
        """No persistent connection is held by this adapter."""


class PostgresEvidenceLedger:
    """Durable Kernel evidence ledger backed by PostgreSQL JSONB rows."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS ois_kernel_evidence_events (
        event_id UUID PRIMARY KEY,
        execution_id UUID NOT NULL,
        event_type TEXT NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL,
        actor TEXT NOT NULL,
        component TEXT NOT NULL,
        data JSONB NOT NULL,
        correlation_id TEXT,
        causation_id TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_ois_kernel_evidence_execution
        ON ois_kernel_evidence_events (execution_id, timestamp, event_id);
    CREATE OR REPLACE FUNCTION ois_reject_kernel_evidence_mutation()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'OIS kernel evidence is append-only';
    END;
    $$;
    DROP TRIGGER IF EXISTS trg_ois_kernel_evidence_immutable
        ON ois_kernel_evidence_events;
    CREATE TRIGGER trg_ois_kernel_evidence_immutable
        BEFORE UPDATE OR DELETE ON ois_kernel_evidence_events
        FOR EACH ROW EXECUTE FUNCTION ois_reject_kernel_evidence_mutation();
    """

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connect = connection_factory

    def initialize(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(self.SCHEMA)

    def append(self, event: EvidenceEvent) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ois_kernel_evidence_events
                    (event_id, execution_id, event_type, timestamp, actor, component,
                     data, correlation_id, causation_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (event_id) DO NOTHING
                """,
                (
                    event.event_id,
                    event.execution_id,
                    event.event_type,
                    event.timestamp,
                    event.actor,
                    event.component,
                    json.dumps(dict(event.data), sort_keys=True),
                    event.correlation_id,
                    event.causation_id,
                ),
            )

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
            "data, correlation_id, causation_id FROM ois_kernel_evidence_events"
        )
        params: tuple[UUID, ...] = ()
        if execution_id is not None:
            query += " WHERE execution_id = %s"
            params = (execution_id,)
        query += " ORDER BY timestamp, event_id"
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        events = []
        for row in rows:
            data = _json_value(row[6])
            timestamp = row[3]
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            events.append(
                EvidenceEvent(
                    event_id=row[0] if isinstance(row[0], UUID) else UUID(str(row[0])),
                    execution_id=(
                        row[1] if isinstance(row[1], UUID) else UUID(str(row[1]))
                    ),
                    event_type=row[2],
                    timestamp=timestamp,
                    actor=row[4],
                    component=row[5],
                    data=data,
                    correlation_id=row[7],
                    causation_id=row[8],
                )
            )
        return tuple(events)

    def count(self, execution_id: UUID | None = None) -> int:
        return len(self.list(execution_id))

    def close(self) -> None:
        """No persistent connection is held by this adapter."""

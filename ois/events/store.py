from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from .contracts import Event


class EventStore(Protocol):
    def append(self, event: Event) -> None: ...
    def get(self, event_id: UUID) -> Event | None: ...
    def list(self, *, tenant: str, limit: int = 100) -> Sequence[Event]: ...


class InMemoryEventStore:
    """Deterministic test/local store with append-only and idempotency semantics."""

    def __init__(self) -> None:
        self._events: dict[UUID, Event] = {}
        self._order: list[UUID] = []

    def append(self, event: Event) -> None:
        event.assert_integrity()
        existing = self._events.get(event.event_id)
        if existing is not None:
            if existing.content_hash != event.content_hash:
                raise ValueError(f"event_id collision with different content: {event.event_id}")
            return
        self._events[event.event_id] = event
        self._order.append(event.event_id)

    def get(self, event_id: UUID) -> Event | None:
        return self._events.get(event_id)

    def list(self, *, tenant: str, limit: int = 100) -> Sequence[Event]:
        if limit < 1:
            raise ValueError("limit must be positive")
        return tuple(
            self._events[event_id]
            for event_id in reversed(self._order)
            if self._events[event_id].tenant == tenant
        )[:limit]


class PostgresEventStore:
    """PostgreSQL event store. Requires psycopg 3 at runtime."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN is required")
        self._dsn = dsn

    def _connect(self) -> object:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL persistence requires the 'psycopg' package") from exc
        return psycopg.connect(self._dsn)

    def append(self, event: Event) -> None:
        event.assert_integrity()
        with self._connect() as conn:  # type: ignore[union-attr]
            conn.execute(
                """INSERT INTO ois_events
                (event_id, timestamp, source, tenant, actor, event_type, payload,
                 provenance, correlation_id, execution_id, policy_context, validation, content_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s::jsonb, %s)
                ON CONFLICT (event_id) DO NOTHING""",
                (
                    str(event.event_id), event.timestamp, event.source, event.tenant, event.actor,
                    event.event_type, event.payload, event.provenance.model_dump(mode="json"),
                    str(event.correlation_id) if event.correlation_id else None,
                    str(event.execution_id) if event.execution_id else None,
                    event.policy_context, event.validation.model_dump(mode="json"), event.content_hash,
                ),
            )

    def get(self, event_id: UUID) -> Event | None:
        with self._connect() as conn:  # type: ignore[union-attr]
            row = conn.execute(
                """SELECT event_id,timestamp,source,tenant,actor,event_type,payload,provenance,
                correlation_id,execution_id,policy_context,validation,content_hash
                FROM ois_events WHERE event_id=%s""",
                (str(event_id),),
            ).fetchone()
        return _row_to_event(row) if row else None

    def list(self, *, tenant: str, limit: int = 100) -> Sequence[Event]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self._connect() as conn:  # type: ignore[union-attr]
            rows = conn.execute(
                """SELECT event_id,timestamp,source,tenant,actor,event_type,payload,provenance,
                correlation_id,execution_id,policy_context,validation,content_hash
                FROM ois_events WHERE tenant=%s ORDER BY timestamp DESC LIMIT %s""",
                (tenant, limit),
            ).fetchall()
        return tuple(_row_to_event(row) for row in rows)


def _row_to_event(row: tuple[object, ...]) -> Event:
    return Event(
        event_id=row[0], timestamp=row[1], source=row[2], tenant=row[3], actor=row[4],
        event_type=row[5], payload=row[6], provenance=row[7], correlation_id=row[8],
        execution_id=row[9], policy_context=row[10], validation=row[11], content_hash=row[12],
    )

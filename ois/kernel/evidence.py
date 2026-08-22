from __future__ import annotations

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

        return result


class EvidenceLedger:
    """
    Append-only in-memory evidence ledger.

    The ledger establishes the Kernel evidence contract. A durable event
    backend can later implement the same append/read semantics.
    """

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

    def list(
        self,
        execution_id: UUID | None = None,
    ) -> tuple[EvidenceEvent, ...]:
        with self._lock:
            if execution_id is None:
                return tuple(self._events)

            return tuple(event for event in self._events if event.execution_id == execution_id)

    def count(
        self,
        execution_id: UUID | None = None,
    ) -> int:
        return len(self.list(execution_id))

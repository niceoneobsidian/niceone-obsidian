"""Dead-letter and deterministic recovery primitives for source ingestion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from ois.domains.social_intelligence.events import CanonicalSourceEvent


@dataclass(frozen=True)
class DeadLetter:
    event: CanonicalSourceEvent
    reason: str
    attempts: int
    failed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


class DeadLetterStore:
    """In-memory recovery store with tenant-scoped replay semantics."""

    def __init__(self) -> None:
        self._items: dict[str, DeadLetter] = {}
        self._lock = RLock()

    def put(self, item: DeadLetter) -> bool:
        with self._lock:
            if item.event.event_id in self._items:
                return False
            self._items[item.event.event_id] = item
            return True

    def get(self, event_id: str) -> DeadLetter:
        with self._lock:
            try:
                return self._items[event_id]
            except KeyError as exc:
                raise KeyError(f"dead-letter event not found: {event_id}") from exc

    def list(self, tenant_id: str, workspace_id: str) -> tuple[DeadLetter, ...]:
        with self._lock:
            return tuple(
                item
                for item in self._items.values()
                if (item.event.tenant_id, item.event.workspace_id) == (tenant_id, workspace_id)
            )

    def remove(self, event_id: str) -> DeadLetter:
        with self._lock:
            return self._items.pop(event_id)

    def size(self) -> int:
        with self._lock:
            return len(self._items)


class SourceRecovery:
    """Retry an intelligence handler and dead-letter exhausted events."""

    def __init__(self, dead_letters: DeadLetterStore, *, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self._dead_letters = dead_letters
        self._max_attempts = max_attempts

    def run(
        self,
        event: CanonicalSourceEvent,
        handler: Callable[[CanonicalSourceEvent], object],
    ) -> bool:
        last_error = "unknown failure"
        for _attempt in range(1, self._max_attempts + 1):
            try:
                handler(event)
                return True
            except Exception as exc:
                last_error = str(exc)
        self._dead_letters.put(
            DeadLetter(event=event, reason=last_error, attempts=self._max_attempts)
        )
        return False

    def replay(self, event_id: str, handler: Callable[[CanonicalSourceEvent], object]) -> bool:
        item = self._dead_letters.get(event_id)
        if not self.run(item.event, handler):
            return False
        self._dead_letters.remove(event_id)
        return True

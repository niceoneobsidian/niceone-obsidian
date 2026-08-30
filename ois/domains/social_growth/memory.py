"""Adapter boundary between Social Growth and OIS-owned memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True)
class MemoryRecord:
    key: str
    value: str
    kind: str
    source: str
    created_at: datetime
    version: int = 1


class MemorySink(Protocol):
    def append(self, record: MemoryRecord) -> None: ...
    def search(
        self, query: str, *, kind: str | None = None, limit: int = 20
    ) -> list[MemoryRecord]: ...


class InMemoryMemoryAdapter:
    """Deterministic reference adapter; OIS production memory can implement the protocol."""

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    def append(self, record: MemoryRecord) -> None:
        self._records.append(record)

    def search(self, query: str, *, kind: str | None = None, limit: int = 20) -> list[MemoryRecord]:
        query_lower = query.lower()
        matches = [
            record
            for record in reversed(self._records)
            if query_lower in f"{record.key} {record.value}".lower()
            and (kind is None or record.kind == kind)
        ]
        return matches[:limit]


def make_record(key: str, value: str, kind: str, source: str) -> MemoryRecord:
    return MemoryRecord(key, value, kind, source, datetime.now(UTC))

"""Append-only in-memory foundation for governed memory."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class MemoryEntry:
    key: str
    version: int
    value: object

class MemoryPlane:
    def __init__(self) -> None:
        self._entries: list[MemoryEntry] = []

    def append(self, key: str, value: object) -> MemoryEntry:
        version = sum(entry.key == key for entry in self._entries) + 1
        entry = MemoryEntry(key, version, value)
        self._entries.append(entry)
        return entry

    def history(self, key: str) -> tuple[MemoryEntry, ...]:
        return tuple(entry for entry in self._entries if entry.key == key)

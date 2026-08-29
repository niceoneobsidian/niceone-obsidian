"""Shared deterministic registry primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from threading import RLock
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RegistryEntry(Generic[T]):
    """Versioned object registered for deterministic lookup."""

    id: str
    version: str
    value: T
    metadata: Mapping[str, object] = field(default_factory=dict)


class Registry(Generic[T]):
    """Thread-safe in-memory registry with explicit versioned identities."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], RegistryEntry[T]] = {}
        self._lock = RLock()

    def _make_entry(
        self,
        object_id: str,
        version: str,
        value: T,
        metadata: Mapping[str, object] | None,
    ) -> RegistryEntry[T]:
        return RegistryEntry(
            id=object_id,
            version=version,
            value=value,
            metadata=dict(metadata or {}),
        )

    def register(
        self,
        object_id: str,
        version: str,
        value: T,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> RegistryEntry[T]:
        if not object_id or not version:
            raise ValueError("registry id and version are required")
        key = (object_id, version)
        with self._lock:
            if key in self._entries:
                raise ValueError(f"already registered: {object_id}@{version}")
            entry = self._make_entry(object_id, version, value, metadata)
            self._entries[key] = entry
            return entry

    def resolve(self, object_id: str, version: str) -> RegistryEntry[T]:
        with self._lock:
            try:
                return self._entries[(object_id, version)]
            except KeyError as exc:
                raise KeyError(f"not registered: {object_id}@{version}") from exc

    def get(self, object_id: str, version: str) -> RegistryEntry[T]:
        return self.resolve(object_id, version)

    def contains(self, object_id: str, version: str) -> bool:
        with self._lock:
            return (object_id, version) in self._entries

    def has(self, object_id: str, version: str) -> bool:
        return self.contains(object_id, version)

    def snapshot(self) -> tuple[RegistryEntry[T], ...]:
        with self._lock:
            return tuple(self._entries[key] for key in sorted(self._entries))

    def list(self) -> tuple[RegistryEntry[T], ...]:
        return self.snapshot()

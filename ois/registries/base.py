"""Shared deterministic registry primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
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
    """Small in-memory registry with explicit versioned identities."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], RegistryEntry[T]] = {}

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
        if key in self._entries:
            raise ValueError(f"already registered: {object_id}@{version}")
        entry = RegistryEntry(
            id=object_id,
            version=version,
            value=value,
            metadata=dict(metadata or {}),
        )
        self._entries[key] = entry
        return entry

    def resolve(self, object_id: str, version: str) -> RegistryEntry[T]:
        try:
            return self._entries[(object_id, version)]
        except KeyError as exc:
            raise KeyError(f"not registered: {object_id}@{version}") from exc

    def contains(self, object_id: str, version: str) -> bool:
        return (object_id, version) in self._entries

    def snapshot(self) -> tuple[RegistryEntry[T], ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))

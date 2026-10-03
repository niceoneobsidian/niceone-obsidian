from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .contracts import PlatformIdentity, utc_now


@dataclass(frozen=True)
class SourceEvent:
    source_id: str
    artifact_id: str
    payload: Any
    identity: PlatformIdentity
    observed_at: object = field(default_factory=utc_now)
    content_hash: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)


class SourceAdapter(Protocol):
    source_id: str

    def health(self) -> bool: ...

    def collect(self, identity: PlatformIdentity, **kwargs: Any) -> list[SourceEvent]: ...


class SourceRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        source_id = adapter.source_id.strip()
        if not source_id:
            raise ValueError("source_id is required")
        if source_id in self._adapters:
            raise ValueError(f"source already registered: {source_id}")
        self._adapters[source_id] = adapter

    def get(self, source_id: str) -> SourceAdapter:
        try:
            return self._adapters[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown source: {source_id}") from exc

    def healthy(self) -> tuple[str, ...]:
        return tuple(
            sorted(source_id for source_id, adapter in self._adapters.items() if adapter.health())
        )

    def collect(
        self, source_id: str, identity: PlatformIdentity, **kwargs: Any
    ) -> list[SourceEvent]:
        adapter = self.get(source_id)
        if not adapter.health():
            raise RuntimeError(f"source is unhealthy: {source_id}")
        events = adapter.collect(identity, **kwargs)
        for event in events:
            if event.identity.tenant_id != identity.tenant_id:
                raise PermissionError("source event crossed tenant boundary")
        return events

    def snapshot(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

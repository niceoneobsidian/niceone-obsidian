"""Common contracts for governed live-source adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from ois.infrastructure.source_gateway import (
    SourceGateway,
    SourceResponse,
    SourceSpec,
)
if TYPE_CHECKING:
    from ois.infrastructure.source_gateway.gateway import SourceGateway, SourceResponse


@dataclass(frozen=True)
class AdapterHealth:
    source_id: str
    healthy: bool
    checked_at: str
    latency_ms: float | None = None
    fresh: bool | None = None
    reason: str | None = None


@dataclass(frozen=True)
class AdapterResult:
    source_id: str
    records: int
    evidence_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    payload_hashes: tuple[str, ...]


class SourceAdapter(Protocol):
    source_id: str

    def ingest(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        gateway: SourceGateway,
        credential_id: str | None = None,
    ) -> AdapterResult: ...


class SourceAdapterRegistry:
    """Deterministic source registry with explicit provider metadata."""

    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}
        self._specs: dict[str, SourceSpec] = {}

    def register(self, adapter: SourceAdapter, spec: SourceSpec | None = None) -> None:
        if adapter.source_id in self._adapters:
            raise ValueError(f"source adapter already registered: {adapter.source_id}")
        self._adapters[adapter.source_id] = adapter
        if spec is not None and spec.source_id != adapter.source_id:
            raise ValueError("source spec source_id must match adapter source_id")
        self._specs[adapter.source_id] = spec or SourceSpec(
            source_id=adapter.source_id,
            provider=adapter.source_id.split(":", 1)[0],
            protocol="unknown",
        )

    def get(self, source_id: str) -> SourceAdapter:
        try:
            return self._adapters[source_id]
        except KeyError as exc:
            raise KeyError(f"source adapter not registered: {source_id}") from exc

    def spec(self, source_id: str) -> SourceSpec:
        try:
            return self._specs[source_id]
        except KeyError as exc:
            raise KeyError(f"source specification not registered: {source_id}") from exc
    def unregister(self, source_id: str) -> None:
        """Remove a connector explicitly; unknown sources are rejected."""
        if source_id not in self._adapters:
            raise KeyError(f"source adapter not registered: {source_id}")
        del self._adapters[source_id]

    def list(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def healthy(self) -> tuple[str, ...]:
        return tuple(source_id for source_id in self.list() if self.get(source_id).health().healthy)

    @staticmethod
    def response(
        source_id: str,
        responses: Sequence[SourceResponse],
    ) -> AdapterResult:
        accepted = [item for item in responses if item.accepted]
        return AdapterResult(
            source_id=source_id,
            records=len(accepted),
            evidence_ids=tuple(item.evidence_id for item in accepted),
            event_ids=tuple(item.event_id for item in accepted),
            payload_hashes=tuple(item.payload_hash for item in accepted),
        )


def utc_now() -> str:
    return datetime.now(UTC).isoformat()

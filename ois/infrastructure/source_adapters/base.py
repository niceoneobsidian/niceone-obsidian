"""Common contracts for governed live-source adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from ois.infrastructure.source_gateway import SourceGateway, SourceResponse


@dataclass(frozen=True)
class AdapterHealth:
    source_id: str
    healthy: bool
    checked_at: str
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

    def health(self) -> AdapterHealth:
        ...

    def ingest(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        gateway: SourceGateway,
        credential_id: str | None = None,
    ) -> AdapterResult:
        ...


class SourceAdapterRegistry:
    """Deterministic registry for live source adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        if adapter.source_id in self._adapters:
            raise ValueError(f"source adapter already registered: {adapter.source_id}")
        self._adapters[adapter.source_id] = adapter

    def get(self, source_id: str) -> SourceAdapter:
        try:
            return self._adapters[source_id]
        except KeyError as exc:
            raise KeyError(f"source adapter not registered: {source_id}") from exc

    def list(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

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

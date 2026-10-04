"""Canonical source event contract for live ingestion."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5


def canonical_event_id(
    tenant_id: str,
    workspace_id: str,
    source_id: str,
    record_id: str,
    payload: Any,
) -> str:
    """Return a stable event ID for the same source observation."""
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return str(
        uuid5(
            NAMESPACE_URL,
            f"{tenant_id}:{workspace_id}:{source_id}:{record_id}:{digest}",
        )
    )


@dataclass(frozen=True)
class SourceEvent:
    """Normalized, immutable representation of one external source observation."""

    event_id: str
    tenant_id: str
    workspace_id: str
    source_id: str
    source_record_id: str
    event_type: str
    payload: dict[str, Any]
    payload_hash: str
    occurred_at: datetime
    received_at: datetime
    schema_version: str = "source.event.v1"
    connector_version: str = "source-v1"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
        source_record_id: str,
        payload: dict[str, Any],
        event_type: str = "source.observation",
        occurred_at: datetime | None = None,
        received_at: datetime | None = None,
        connector_version: str = "source-v1",
        metadata: dict[str, Any] | None = None,
    ) -> SourceEvent:
        from .evidence import canonical_hash

        received = received_at or datetime.now(UTC)
        return cls(
            event_id=canonical_event_id(
                tenant_id, workspace_id, source_id, source_record_id, payload
            ),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
            source_record_id=source_record_id,
            event_type=event_type,
            payload=dict(payload),
            payload_hash=canonical_hash(payload),
            occurred_at=occurred_at or received,
            received_at=received,
            connector_version=connector_version,
            metadata=dict(metadata or {}),
        )

    def as_payload(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "source_id": self.source_id,
            "source_record_id": self.source_record_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "payload_hash": self.payload_hash,
            "occurred_at": self.occurred_at.isoformat(),
            "received_at": self.received_at.isoformat(),
            "schema_version": self.schema_version,
            "connector_version": self.connector_version,
            "metadata": self.metadata,
        }

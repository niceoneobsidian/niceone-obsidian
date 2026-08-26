from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from ..kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ..kernel.types import InvocationStatus
from .contracts import Event, EventProvenance, EventValidation
from .store import EventStore


class EventIngestion:
    """Normalize, validate, hash, and persist observations at the OIS perception boundary."""

    contract = CapabilityContract(
        capability_id="event_ingestion",
        version="1.0.0",
        description="Canonical system event normalization, validation and persistence.",
        permissions=("events:write",),
        idempotent=True,
    )

    def __init__(self, store: EventStore, *, validator_id: str = "ois.event_ingestion") -> None:
        self._store = store
        self._validator_id = validator_id

    def ingest(
        self,
        *,
        source: str,
        tenant: str,
        actor: str,
        event_type: str,
        payload: dict[str, Any],
        observed_at: datetime,
        source_ref: str,
        source_kind: str,
        correlation_id: UUID | None = None,
        execution_id: UUID | None = None,
        policy_context: dict[str, Any] | None = None,
        raw_content_hash: str | None = None,
        sequence: int | None = None,
    ) -> Event:
        timestamp = _utc(observed_at)
        provenance = EventProvenance(
            source_ref=source_ref,
            source_kind=source_kind,
            observed_at=timestamp,
            collector=self._validator_id,
            sequence=sequence,
            raw_content_hash=raw_content_hash,
        )
        validation = EventValidation(
            valid=True,
            validated_at=datetime.now(timezone.utc),
            validator=self._validator_id,
        )
        event = Event(
            timestamp=timestamp,
            source=source,
            tenant=tenant,
            actor=actor,
            event_type=event_type,
            payload=payload,
            provenance=provenance,
            correlation_id=correlation_id,
            execution_id=execution_id,
            policy_context=policy_context or {},
            validation=validation,
        ).with_content_hash()
        event.assert_integrity()
        self._store.append(event)
        return event

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        try:
            data = dict(request.input)
            event = self.ingest(**data)
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.SUCCESS,
                output=event.model_dump(mode="json"),
            )
        except Exception as exc:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": type(exc).__name__, "message": str(exc)},
            )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")
    return value.astimezone(timezone.utc)

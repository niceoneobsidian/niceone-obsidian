"""Source Gateway facade and execution bounds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .credentials import CredentialResolver, TenantScope
from .evidence import RawEvidence, RawEvidenceWriter, canonical_hash
from .limits import RateLimitPolicy
from .outbox import OutboxEvent, OutboxStore


@dataclass(frozen=True)
class SourceRequest:
    source_id: str
    credential: str
    payload: dict[str, Any]
    tenant_id: str | None = None


@dataclass(frozen=True)
class SourceResponse:
    accepted: bool
    evidence_id: str
    event_id: str
    payload_hash: str
    error: str | None = None


class SourceGateway:
    def __init__(
        self,
        credentials: CredentialResolver,
        evidence: RawEvidenceWriter,
        outbox: OutboxStore,
        rate_limits: dict[str, RateLimitPolicy] | None = None,
    ) -> None:
        self._credentials = credentials
        self._evidence = evidence
        self._outbox = outbox
        self._rate_limits = rate_limits or {}

    def _id(self) -> str:
        return str(uuid4())

    def ingest(self, request: SourceRequest) -> SourceResponse:
        if request.tenant_id:
            scope = TenantScope(tenant_id=request.tenant_id)
            if not scope.allows(request.credential):
                raise PermissionError("credential belongs to another tenant")
            self._credentials.resolve(request.credential, scope)

        bucket = self._rate_limits.get(request.source_id)
        if bucket is not None and not bucket.acquire():
            return SourceResponse(False, "", "", "", "rate_limited")

        evidence_id = self._id()
        event_id = self._id()
        payload_hash = canonical_hash(request.payload)

        evidence = RawEvidence(
            evidence_id=evidence_id,
            source_id=request.source_id,
            payload=request.payload,
            captured_at=datetime.now(UTC),
            payload_hash=payload_hash,
        )

        event = OutboxEvent(
            event_id=event_id,
            aggregate_type="source_ingest",
            aggregate_id=evidence_id,
            event_type="raw_evidence_ingested",
            payload={
                "evidence_id": evidence_id,
                "source_id": request.source_id,
                "payload_hash": payload_hash,
            },
            created_at=datetime.now(UTC),
        )

        commit_ingest = getattr(self._evidence, "commit_ingest", None)
        outbox_db = getattr(self._outbox, "_db", None)
        evidence_db = getattr(self._evidence, "_db", None)

        if callable(commit_ingest) and outbox_db is not None and outbox_db is evidence_db:
            accepted = commit_ingest(evidence, event)
        else:
            accepted = self._evidence.append(evidence)
            if accepted and not self._outbox.append(event):
                raise RuntimeError(
                    "evidence committed but outbox append failed; "
                    "use SQLiteSourceLedger for atomicity"
                )
        if not accepted:
            return SourceResponse(False, evidence_id, event_id, payload_hash, "duplicate_evidence")
        return SourceResponse(True, evidence_id, event_id, payload_hash)

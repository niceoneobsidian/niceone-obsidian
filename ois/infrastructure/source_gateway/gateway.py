"""Source Gateway facade and execution bounds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from .credentials import CredentialRef, CredentialResolver, TenantScope
from .evidence import RawEvidence, RawEvidenceWriter, canonical_hash
from .limits import RateLimitPolicy
from .outbox import OutboxEvent, OutboxStore


@dataclass(frozen=True)
class SourceRequest:
    tenant_id: str
    workspace_id: str
    source_type: str
    source_record_id: str
    payload: dict[str, Any]
    credential: CredentialRef | None = None
    connector_version: str = "v1"
    schema_version: str = "v1"

    @property
    def source_id(self) -> str:
        return f"{self.source_type}:{self.source_record_id}"


@dataclass(frozen=True)
class SourceResponse:
    accepted: bool
    evidence_id: str
    event_id: str
    payload_hash: str
    reason: str | None = None


class SourceGateway:
    def __init__(
        self,
        credentials: CredentialResolver | None = None,
        evidence: RawEvidenceWriter | None = None,
        outbox: OutboxStore | None = None,
        rate_limits: dict[str, RateLimitPolicy] | None = None,
    ) -> None:
        self._credentials = credentials
        self._evidence = evidence
        self._outbox = outbox
        self._rate_limits = rate_limits or {}

    def _id(self) -> str:
        return str(uuid4())

    def ingest(self, request: SourceRequest) -> SourceResponse:
        if request.credential and self._credentials:
            scope = TenantScope(
                tenant_id=request.tenant_id,
                workspace_id=request.workspace_id,
            )
            if request.credential.tenant_id != request.tenant_id:
                raise PermissionError("credential belongs to another tenant")
            self._credentials.resolve(request.credential)

        bucket = self._rate_limits.get(request.source_id)
        if bucket is not None and not bucket.allow():
            return SourceResponse(False, "", "", "", "rate_limited")

        evidence_id = self._id()
        event_id = self._id()
        payload_hash = canonical_hash(request.payload)

        evidence = RawEvidence(
            evidence_id=evidence_id,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            source_type=request.source_type,
            source_record_id=request.source_record_id,
            payload=request.payload,
            captured_at=datetime.now(UTC),
            payload_hash=payload_hash,
        )

        event = OutboxEvent(
            event_id=event_id,
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

        if callable(commit_ingest) and cast(object, self._outbox) is cast(object, self._evidence):
            accepted = commit_ingest(evidence, event)
        else:
            accepted = self._evidence.append(evidence) if self._evidence else True
            outbox_ok = self._outbox.append(event) if self._outbox else True
            if accepted and not outbox_ok:
                raise RuntimeError(
                    "evidence committed but outbox append failed; "
                    "use SQLiteSourceLedger for atomicity"
                )
        if not accepted:
            return SourceResponse(False, evidence_id, event_id, payload_hash, "duplicate_evidence")
        return SourceResponse(True, evidence_id, event_id, payload_hash)

"""Source Gateway facade and execution bounds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid4, uuid5

from .credentials import CredentialRef, CredentialResolver, TenantScope
from .evidence import RawEvidence, RawEvidenceWriter, canonical_hash
from .limits import RateLimitPolicy, TokenBucket
from .outbox import OutboxEvent, OutboxStore


@dataclass(frozen=True)
class SourceRequest:
    tenant_id: str
    workspace_id: str
    source_type: str = ""
    source_record_id: str = ""
    payload: dict[str, Any] | None = None
    credential: CredentialRef | None = None
    connector_version: str = "v1"
    schema_version: str = "v1"
    source_id: str = ""

    def __post_init__(self) -> None:
        if self.payload is None:
            object.__setattr__(self, "payload", {})
        if not self.source_id and self.source_type:
            object.__setattr__(self, "source_id", f"{self.source_type}:{self.source_record_id}")


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
        self._rate_limiters: dict[str, TokenBucket] = {}
        if rate_limits:
            for key, policy in rate_limits.items():
                self._rate_limiters[key] = (
                    policy if isinstance(policy, TokenBucket) else TokenBucket(policy)
                )

    def _id(self) -> str:
        return str(uuid4())

    def ingest(self, request: SourceRequest) -> SourceResponse:
        scope = TenantScope(
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
        )

        if request.credential and self._credentials:
            if request.credential.tenant_id != request.tenant_id:
                raise PermissionError("credential belongs to another tenant")
            self._credentials.resolve(request.credential, scope)

        bucket = self._rate_limiters.get(request.source_type) or self._rate_limiters.get(
            request.source_id
        )
        if bucket is not None and not bucket.acquire():
            return SourceResponse(False, "", "", "", "rate_limited")

        payload_hash = canonical_hash(request.payload)
        evidence_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{request.tenant_id}:{request.workspace_id}:{request.source_id}:"
                f"{request.source_record_id}:{payload_hash}",
            )
        )
        event_id = str(uuid5(NAMESPACE_URL, f"source-outbox:{evidence_id}"))

        evidence = RawEvidence(
            evidence_id=evidence_id,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            source_id=request.source_id,
            source_record_id=request.source_record_id,
            payload=request.payload or {},
            payload_hash=payload_hash,
            collected_at=datetime.now(UTC),
            connector_version=request.connector_version,
            schema_version=request.schema_version,
            ingestion_run_id=self._id(),
        )

        event = OutboxEvent(
            event_id=event_id,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            aggregate_id=evidence_id,
            event_type="source.raw_evidence.created",
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

from __future__ import annotations

from typing import cast

"""Source Gateway: governed front door for production external sources."""


from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .credentials import CredentialRef, CredentialResolver, TenantScope
from .evidence import RawEvidence, RawEvidenceWriter, canonical_hash
from .limits import TokenBucket
from .outbox import OutboxEvent, OutboxStore


@dataclass(frozen=True)
class SourceRequest:
    tenant_id: str
    workspace_id: str
    source_id: str
    source_record_id: str
    payload: Any
    credential: CredentialRef | None = None
    connector_version: str = "unknown"
    schema_version: str = "1"
    ingestion_run_id: str = ""


@dataclass(frozen=True)
class SourceResponse:
    accepted: bool
    evidence_id: str
    event_id: str
    payload_hash: str
    reason: str | None = None


class SourceGateway:
    """Captures source payloads before downstream normalization.

    A successful ingest writes raw evidence and its outbox event as one logical
    unit. The concrete SQLite stores are reference implementations; production
    deployment should bind equivalent contracts to the durable application DB.
    """

    def __init__(
        self,
        *,
        evidence: RawEvidenceWriter,
        outbox: OutboxStore,
        credentials: CredentialResolver | None = None,
        rate_limits: dict[str, TokenBucket] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._evidence = evidence
        self._outbox = outbox
        self._credentials = credentials
        self._rate_limits = dict(rate_limits or {})
        self._id = id_factory or (lambda: str(uuid4()))

    def ingest(self, request: SourceRequest) -> SourceResponse:
        scope = TenantScope(request.tenant_id, request.workspace_id)
        if request.credential is not None:
            if self._credentials is None:
                raise RuntimeError("credential resolver is required for credentialed sources")
            if request.credential.tenant_id != scope.tenant_id:
                raise PermissionError("credential belongs to another tenant")
            self._credentials.resolve(request.credential, scope)

        bucket = self._rate_limits.get(request.source_id)
        if bucket is not None and not bucket.acquire():
            return SourceResponse(False, "", "", "", "rate_limited")

        evidence_id = self._id()
        event_id = self._id()
        payload_hash = canonical_hash(request.payload)
        evidence = RawEvidence(
            evidence_id,
            scope.tenant_id,
            scope.workspace_id,
            request.source_id,
            request.source_record_id,
            request.payload,
            payload_hash,
            datetime.now(UTC),
            request.connector_version,
            request.schema_version,
            request.ingestion_run_id or self._id(),
        )
        event = OutboxEvent(
            event_id,
            scope.tenant_id,
            scope.workspace_id,
            "source.raw_evidence.created",
            evidence_id,
            {
                "evidence_id": evidence_id,
                "source_id": request.source_id,
                "source_record_id": request.source_record_id,
                "payload_hash": payload_hash,
            },
            evidence.collected_at,
        )
        commit_ingest = getattr(self._evidence, "commit_ingest", None)
        if callable(commit_ingest) and cast(object, self._outbox) is cast(object, self._evidence):
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

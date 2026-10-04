"""Source Gateway facade and execution bounds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from .auth import CredentialMaterial
from .credentials import CredentialRef, CredentialResolver, TenantScope
from .evidence import RawEvidence, RawEvidenceWriter, canonical_hash
from .events import SourceEvent
from .idempotency import IdempotencyStore
from .limits import RateLimitPolicy, TokenBucket
from .outbox import OutboxEvent, OutboxStore
from .rate_limits import RateLimitManager


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
    event_type: str = "source.observation"
    idempotency_key: str | None = None

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
        *,
        idempotency: IdempotencyStore | None = None,
        rate_limit_manager: RateLimitManager | None = None,
    ) -> None:
        self._credentials = credentials
        self._evidence = evidence
        self._outbox = outbox
        self._idempotency = idempotency
        self._rate_limit_manager = rate_limit_manager
        self._rate_limiters: dict[str, TokenBucket] = {}
        if rate_limits:
            for key, policy in rate_limits.items():
                self._rate_limiters[key] = (
                    policy if isinstance(policy, TokenBucket) else TokenBucket(policy)
                )

    def _id(self) -> str:
        from uuid import uuid4

        return str(uuid4())

    def resolve_credential(self, ref: CredentialRef, scope: TenantScope) -> CredentialMaterial:
        """Resolve tenant-scoped secret material for an authentication strategy."""
        if ref.tenant_id != scope.tenant_id:
            raise PermissionError("credential belongs to another tenant")
        if self._credentials is None:
            raise RuntimeError("credential resolver is not configured")
        return CredentialMaterial(self._credentials.resolve(ref, scope))

    def ingest(self, request: SourceRequest) -> SourceResponse:
        scope = TenantScope(
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
        )

        if request.credential and self._credentials:
            self.resolve_credential(request.credential, scope)

        payload = request.payload or {}
        event = SourceEvent.from_payload(
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            source_id=request.source_id,
            source_record_id=request.source_record_id,
            payload=payload,
            event_type=request.event_type,
            connector_version=request.connector_version,
        )
        payload_hash = event.payload_hash
        evidence_id = event.event_id
        event_id = event.event_id

        rate_key = f"{request.tenant_id}:{request.workspace_id}:{request.source_id}"
        if self._rate_limit_manager is not None:
            decision = self._rate_limit_manager.allow(rate_key)
            if not decision.allowed:
                return SourceResponse(False, "", "", "", "rate_limited")
        else:
            bucket = self._rate_limiters.get(request.source_id) or self._rate_limiters.get(
                request.source_type
            ) or self._rate_limiters.get(rate_key)
            if bucket is not None and not bucket.acquire():
                return SourceResponse(False, "", "", "", "rate_limited")

        idempotency_claimed = False
        if request.idempotency_key and self._idempotency is not None:
            if not self._idempotency.claim(
                tenant_id=request.tenant_id,
                workspace_id=request.workspace_id,
                key=request.idempotency_key,
                event_id=event_id,
            ):
                existing = self._idempotency.get(
                    tenant_id=request.tenant_id,
                    workspace_id=request.workspace_id,
                    key=request.idempotency_key,
                )
                return SourceResponse(
                    False,
                    existing.event_id if existing else evidence_id,
                    existing.event_id if existing else event_id,
                    payload_hash,
                    "duplicate_idempotency",
                )
            # The claim is a reservation. It is retained only if durable
            # evidence/outbox acceptance succeeds and released on failure.
            idempotency_claimed = True

        evidence = RawEvidence(
            evidence_id=evidence_id,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            source_id=request.source_id,
            source_record_id=request.source_record_id,
            payload=payload,
            payload_hash=payload_hash,
            collected_at=event.received_at,
            connector_version=request.connector_version,
            schema_version=request.schema_version,
            ingestion_run_id=self._id(),
        )

        outbox_payload = event.as_payload()
        outbox_payload["evidence_id"] = evidence_id
        outbox_event = OutboxEvent(
            event_id=event_id,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            aggregate_id=evidence_id,
            # This is the durable acceptance event consumed by existing
            # evidence-graph projectors. The canonical source event type is
            # preserved inside outbox_payload["event_type"].
            event_type="source.raw_evidence.created",
            payload=outbox_payload,
            created_at=event.received_at,
        )

        try:
            commit_ingest = getattr(self._evidence, "commit_ingest", None)
            if callable(commit_ingest) and cast(object, self._outbox) is cast(object, self._evidence):
                accepted = commit_ingest(evidence, outbox_event)
            else:
                accepted = self._evidence.append(evidence) if self._evidence else True
                outbox_ok = self._outbox.append(outbox_event) if self._outbox else True
                if accepted and not outbox_ok:
                    raise RuntimeError(
                        "evidence committed but outbox append failed; "
                        "use SQLiteSourceLedger for atomicity"
                    )
        except Exception:
            if idempotency_claimed and self._idempotency is not None and request.idempotency_key:
                self._idempotency.release(
                    tenant_id=request.tenant_id,
                    workspace_id=request.workspace_id,
                    key=request.idempotency_key,
                    event_id=event_id,
                )
            raise

        if not accepted:
            if idempotency_claimed and self._idempotency is not None and request.idempotency_key:
                self._idempotency.release(
                    tenant_id=request.tenant_id,
                    workspace_id=request.workspace_id,
                    key=request.idempotency_key,
                    event_id=event_id,
                )
            return SourceResponse(False, evidence_id, event_id, payload_hash, "duplicate_evidence")
        return SourceResponse(True, evidence_id, event_id, payload_hash)

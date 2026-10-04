"""Source Gateway facade and execution bounds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid4, uuid5

from ois.domains.social_intelligence.events import CanonicalSourceEvent

from .auth import Authenticator, AuthRequest, AuthScheme, CredentialMaterial
from .contracts import SourceProvenance
from .credentials import CredentialRef, CredentialResolver, TenantScope
from .evidence import RawEvidence, RawEvidenceWriter, canonical_hash
from .limits import RateLimitPolicy, TokenBucket
from .manager import AuthPolicy, CredentialAuthManager
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
    provenance: SourceProvenance | None = None
    observed_at: datetime | None = None
    rate_limit_lease: str | None = None

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
        intelligence_pipeline: object | None = None,
        auth_manager: CredentialAuthManager | None = None,
    ) -> None:
        self._credentials = credentials
        self._auth_manager = auth_manager or (
            CredentialAuthManager(credentials) if credentials else None
        )
        self._evidence = evidence
        self._intelligence_pipeline = intelligence_pipeline
        self._outbox = outbox
        self._rate_limiters: dict[str, TokenBucket] = {}
        self._leases: dict[str, tuple[str, str]] = {}
        if rate_limits:
            for key, policy in rate_limits.items():
                self._rate_limiters[key] = (
                    policy if isinstance(policy, TokenBucket) else TokenBucket(policy)
                )

    def _id(self) -> str:
        return str(uuid4())

    def resolve_credential(self, ref: CredentialRef, scope: TenantScope) -> CredentialMaterial:
        """Resolve tenant-scoped secret material for an authentication strategy."""
        if ref.tenant_id != scope.tenant_id:
            raise PermissionError("credential belongs to another tenant")
        if self._auth_manager is None:
            raise RuntimeError("credential resolver is not configured")
        return self._auth_manager.resolve(ref, scope)

    def authenticate_request(
        self,
        request: AuthRequest,
        ref: CredentialRef,
        scope: TenantScope,
        scheme: AuthScheme,
        *,
        options: dict[str, object] | None = None,
        client_id: str | None = None,
        token_type: str = "Bearer",
        authenticator: Authenticator | None = None,
    ) -> AuthRequest:
        """Authenticate a request through the central credential boundary."""
        if self._auth_manager is None:
            raise RuntimeError("credential auth manager is not configured")
        return self._auth_manager.authenticate(
            request,
            ref,
            scope,
            AuthPolicy(scheme, options),
            client_id=client_id,
            token_type=token_type,
            authenticator=authenticator,
        )

    def rate_limit_configured(self, *, source_type: str = "", source_id: str = "") -> bool:
        return self._select_rate_limiter(source_type=source_type, source_id=source_id) is not None

    def acquire_rate_limit(self, *, source_type: str = "", source_id: str = "") -> str | None:
        bucket = self._select_rate_limiter(source_type=source_type, source_id=source_id)
        if bucket is None:
            return None
        if not bucket.acquire():
            return None
        lease = str(uuid4())
        self._leases[lease] = (source_type, source_id)
        return lease

    def _select_rate_limiter(self, *, source_type: str, source_id: str) -> TokenBucket | None:
        return self._rate_limiters.get(source_type) or self._rate_limiters.get(source_id)

    def ingest(self, request: SourceRequest) -> SourceResponse:
        scope = TenantScope(
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
        )

        credential_verified = False
        if request.credential and self._auth_manager:
            self.resolve_credential(request.credential, scope)
            credential_verified = True

        if request.rate_limit_lease is not None:
            lease_scope = self._leases.pop(request.rate_limit_lease, None)
            if lease_scope != (request.source_type, request.source_id):
                return SourceResponse(False, "", "", "", "invalid_rate_limit_lease")
        else:
            configured = self._select_rate_limiter(
                source_type=request.source_type,
                source_id=request.source_id,
            )
            if configured is not None:
                lease = self.acquire_rate_limit(
                    source_type=request.source_type,
                    source_id=request.source_id,
                )
                if lease is None:
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
        collected_at = request.observed_at or datetime.now(UTC)

        evidence = RawEvidence(
            evidence_id=evidence_id,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            source_id=request.source_id,
            source_record_id=request.source_record_id,
            payload=request.payload or {},
            payload_hash=payload_hash,
            collected_at=collected_at,
            connector_version=request.connector_version,
            schema_version=request.schema_version,
            ingestion_run_id=self._id(),
        )

        event_payload: dict[str, Any] = {
            "evidence_id": evidence_id,
            "source_id": request.source_id,
            "payload_hash": payload_hash,
        }
        if request.provenance:
            event_payload["provenance"] = request.provenance.as_dict()

        event = OutboxEvent(
            event_id=event_id,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            aggregate_id=evidence_id,
            event_type="source.raw_evidence.created",
            payload=event_payload,
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

        if self._intelligence_pipeline is not None:
            process = getattr(self._intelligence_pipeline, "process", None)
            if callable(process):
                canonical_event = CanonicalSourceEvent(
                    event_id=event_id,
                    tenant_id=request.tenant_id,
                    workspace_id=request.workspace_id,
                    source_id=request.source_id,
                    source_record_id=request.source_record_id,
                    event_type="source.raw_evidence.created",
                    payload=request.payload or {},
                    payload_hash=payload_hash,
                    connector_version=request.connector_version,
                    schema_version=request.schema_version,
                )
                result = process(canonical_event, credential_verified=credential_verified)
                if not getattr(result, "accepted", False):
                    return SourceResponse(
                        True,
                        evidence_id,
                        event_id,
                        payload_hash,
                        getattr(result, "reason", "intelligence_pipeline_rejected"),
                    )
        return SourceResponse(True, evidence_id, event_id, payload_hash)

"""Source Gateway module exports."""

from __future__ import annotations

from .auth import (
    ApiKeyAuth,
    Authenticator,
    AuthRequest,
    AuthScheme,
    BasicClientAuth,
    BearerAuth,
    CredentialMaterial,
    HmacAuth,
    OAuth2Auth,
    authenticator_for,
)
from .contracts import FreshnessPolicy, SourceProvenance, SourceSpec
from .credentials import CredentialRef, CredentialResolver, InMemoryCredentialResolver, TenantScope
from .cursors import SourceCursor, SQLiteCursorStore
from .events import SourceEvent, canonical_event_id
from .evidence import RawEvidence, RawEvidenceWriter, SQLiteRawEvidenceWriter, canonical_hash
from .gateway import SourceGateway, SourceRequest, SourceResponse
from .idempotency import (
    IdempotencyRecord,
    IdempotencyStore,
    PostgresIdempotencyStore,
    SQLiteIdempotencyStore,
)
from .ledger import SQLiteSourceLedger
from .limits import RateLimitPolicy, RateLimitState, TokenBucket
from .manager import AuthPolicy, CredentialAuthManager
from .outbox import OutboxEvent, OutboxStore, SQLiteOutboxStore
from .postgres import PostgresSourceLedger
from .rate_limits import RateLimitDecision, RateLimitManager
from .webhook_security import WebhookSecurity, WebhookSecurityPolicy

__all__ = [
    "ApiKeyAuth",
    "AuthPolicy",
    "CredentialAuthManager",
    "AuthRequest",
    "AuthScheme",
    "Authenticator",
    "BearerAuth",
    "BasicClientAuth",
    "CredentialMaterial",
    "HmacAuth",
    "OAuth2Auth",
    "authenticator_for",
    "CredentialRef",
    "CredentialResolver",
    "FreshnessPolicy",
    "InMemoryCredentialResolver",
    "OutboxEvent",
    "OutboxStore",
    "PostgresSourceLedger",
    "RateLimitDecision",
    "RateLimitManager",
    "RateLimitPolicy",
    "RateLimitState",
    "RawEvidence",
    "RawEvidenceWriter",
    "SQLiteCursorStore",
    "PostgresIdempotencyStore",
    "SQLiteIdempotencyStore",
    "SQLiteOutboxStore",
    "SQLiteRawEvidenceWriter",
    "SQLiteSourceLedger",
    "SourceCursor",
    "SourceEvent",
    "SourceGateway",
    "SourceProvenance",
    "SourceRequest",
    "SourceResponse",
    "SourceSpec",
    "TenantScope",
    "TokenBucket",
    "IdempotencyRecord",
    "IdempotencyStore",
    "WebhookSecurity",
    "WebhookSecurityPolicy",
    "canonical_event_id",
    "canonical_hash",
]

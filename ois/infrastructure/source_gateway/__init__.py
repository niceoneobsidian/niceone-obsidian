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
from .credentials import CredentialRef, CredentialResolver, InMemoryCredentialResolver, TenantScope
from .cursors import SourceCursor, SQLiteCursorStore
from .evidence import RawEvidence, RawEvidenceWriter, SQLiteRawEvidenceWriter, canonical_hash
from .events import SourceEvent, canonical_event_id
from .gateway import SourceGateway, SourceRequest, SourceResponse
from .idempotency import (
    IdempotencyRecord,
    IdempotencyStore,
    PostgresIdempotencyStore,
    SQLiteIdempotencyStore,
)
from .ledger import SQLiteSourceLedger
from .limits import RateLimitPolicy, RateLimitState, TokenBucket
from .outbox import OutboxEvent, OutboxStore, SQLiteOutboxStore
from .postgres import PostgresSourceLedger
from .rate_limits import RateLimitDecision, RateLimitManager
from .socket import ApiSourceSocket, SocketStatus
from .webhook_security import WebhookSecurity, WebhookSecurityPolicy

__all__ = [
    "ApiKeyAuth",
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
    "ApiSourceSocket",
    "SocketStatus",
    "SourceGateway",
    "SourceRequest",
    "SourceResponse",
    "TenantScope",
    "TokenBucket",
    "IdempotencyRecord",
    "IdempotencyStore",
    "WebhookSecurity",
    "WebhookSecurityPolicy",
    "canonical_event_id",
    "canonical_hash",
]

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
from .gateway import SourceGateway, SourceRequest, SourceResponse
from .ledger import SQLiteSourceLedger
from .limits import RateLimitPolicy, RateLimitState, TokenBucket
from .outbox import OutboxEvent, OutboxStore, SQLiteOutboxStore
from .postgres import PostgresSourceLedger
from .socket import ApiSourceSocket, SocketStatus

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
    "RateLimitPolicy",
    "RateLimitState",
    "RawEvidence",
    "RawEvidenceWriter",
    "SQLiteCursorStore",
    "SQLiteOutboxStore",
    "SQLiteRawEvidenceWriter",
    "SQLiteSourceLedger",
    "SourceCursor",
    "ApiSourceSocket",
    "SocketStatus",
    "SourceGateway",
    "SourceRequest",
    "SourceResponse",
    "TenantScope",
    "TokenBucket",
    "canonical_hash",
]

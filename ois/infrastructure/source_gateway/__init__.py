"""Phase 1 production source gateway primitives.

The gateway owns credential references, tenant scoping, rate limits,
raw-evidence capture, and transactional outbox delivery. It intentionally
contains no platform-specific connector implementation.
"""

from .credentials import CredentialRef, InMemoryCredentialResolver, TenantScope
from .cursors import SourceCursor, SQLiteCursorStore
from .evidence import RawEvidence, RawEvidenceWriter, SQLiteRawEvidenceWriter
from .gateway import SourceGateway, SourceRequest, SourceResponse
from .ledger import SQLiteSourceLedger
from .limits import RateLimitPolicy, RateLimitState
from .outbox import OutboxEvent, OutboxStore, SQLiteOutboxStore

__all__ = [
    "InMemoryCredentialResolver",
    "CredentialRef",
    "TenantScope",
    "SourceGateway",
    "SourceRequest",
    "SourceResponse",
    "RateLimitPolicy",
    "RateLimitState",
    "RawEvidence",
    "RawEvidenceWriter",
    "SQLiteRawEvidenceWriter",
    "OutboxEvent",
    "OutboxStore",
    "SQLiteOutboxStore",
    "SQLiteSourceLedger",
    "SourceCursor",
    "SQLiteCursorStore",
]

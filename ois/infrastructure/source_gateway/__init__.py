"""Phase 1 production source gateway primitives.

The gateway owns credential references, tenant scoping, rate limits,
raw-evidence capture, and transactional outbox delivery. It intentionally
contains no platform-specific connector implementation.
"""

from .credentials import CredentialRef, TenantScope
from .gateway import SourceGateway, SourceRequest, SourceResponse
from .limits import RateLimitPolicy, RateLimitState
from .evidence import RawEvidence, RawEvidenceWriter, SQLiteRawEvidenceWriter
from .outbox import OutboxEvent, OutboxStore, SQLiteOutboxStore
from .ledger import SQLiteSourceLedger
from .cursors import SourceCursor, SQLiteCursorStore

__all__ = [
    "CredentialRef", "TenantScope", "SourceGateway", "SourceRequest", "SourceResponse",
    "RateLimitPolicy", "RateLimitState", "RawEvidence", "RawEvidenceWriter",
    "SQLiteRawEvidenceWriter", "OutboxEvent", "OutboxStore", "SQLiteOutboxStore", "SQLiteSourceLedger", "SourceCursor", "SQLiteCursorStore",
]

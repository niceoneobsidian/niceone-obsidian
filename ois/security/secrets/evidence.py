"""Tamper-evident audit and security evidence ledger."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import hmac
import json

@dataclass(frozen=True, slots=True)
class EvidenceEvent:
    sequence: int
    event_type: str
    actor: str
    resource: str
    occurred_at: str
    metadata: dict
    previous_hash: str
    digest: str

class EvidenceLedger:
    def __init__(self, key: bytes | None = None) -> None:
        self.key = key
        self._events: list[EvidenceEvent] = []

    def append(self, event_type: str, actor: str, resource: str, metadata: dict | None = None) -> EvidenceEvent:
        previous = self._events[-1].digest if self._events else "GENESIS"
        payload = {"sequence": len(self._events), "event_type": event_type, "actor": actor, "resource": resource, "occurred_at": datetime.now(UTC).isoformat(), "metadata": metadata or {}, "previous_hash": previous}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        digest = hmac.new(self.key, raw, hashlib.sha256).hexdigest() if self.key else hashlib.sha256(raw).hexdigest()
        item = EvidenceEvent(digest=digest, **payload)
        self._events.append(item)
        return item

    def verify(self) -> bool:
        previous = "GENESIS"
        for event in self._events:
            payload = asdict(event)
            payload.pop("digest")
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            expected = hmac.new(self.key, raw, hashlib.sha256).hexdigest() if self.key else hashlib.sha256(raw).hexdigest()
            if event.previous_hash != previous or not hmac.compare_digest(event.digest, expected):
                return False
            previous = event.digest
        return True

    def export(self) -> list[dict]:
        return [asdict(event) for event in self._events]

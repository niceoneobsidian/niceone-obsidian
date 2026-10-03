from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Any

from .contracts import Lineage, PlatformIdentity, utc_now


@dataclass(frozen=True)
class EvidenceArtifact:
    evidence_id: str
    identity: PlatformIdentity
    artifact_type: str
    payload: Any
    content_hash: str
    lineage: Lineage
    recorded_at: datetime = field(default_factory=utc_now)
    live: bool = True

    @staticmethod
    def digest(payload: Any) -> str:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()


class EvidenceStore:
    def __init__(self) -> None:
        self._items: dict[str, EvidenceArtifact] = {}
        self._lock = RLock()

    def append(
        self,
        identity: PlatformIdentity,
        artifact_type: str,
        payload: Any,
        *,
        parent_ids: tuple[str, ...] = (),
        live: bool = True,
    ) -> EvidenceArtifact:
        with self._lock:
            for parent_id in parent_ids:
                parent = self._items.get(parent_id)
                if parent is None:
                    raise ValueError(f"unknown evidence parent: {parent_id}")
                if parent.identity.tenant_id != identity.tenant_id:
                    raise PermissionError("cross-tenant evidence lineage is forbidden")
            eid = str(uuid.uuid4())
            item = EvidenceArtifact(
                eid,
                identity,
                artifact_type,
                payload,
                EvidenceArtifact.digest(payload),
                Lineage(eid, parent_ids),
                live=live,
            )
            self._items[eid] = item
            return item

    def get(self, evidence_id: str) -> EvidenceArtifact:
        return self._items[evidence_id]

    def verify(self, evidence_id: str) -> bool:
        item = self.get(evidence_id)
        return item.content_hash == EvidenceArtifact.digest(item.payload)

    def list(self, tenant_id: str) -> tuple[EvidenceArtifact, ...]:
        return tuple(x for x in self._items.values() if x.identity.tenant_id == tenant_id)

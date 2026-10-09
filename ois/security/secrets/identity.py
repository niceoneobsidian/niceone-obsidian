"""Workload identity, trust and federation primitives."""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
import secrets

@dataclass(frozen=True, slots=True)
class WorkloadIdentity:
    id: str
    subject: str
    workload_id: str
    issuer: str
    issued_at: datetime
    expires_at: datetime
    trust_score: int = 0
    public_key: str | None = None
    revoked_at: datetime | None = None

class WorkloadIdentityService:
    def __init__(self) -> None:
        self._identities: dict[str, WorkloadIdentity] = {}

    def register(self, subject: str, workload_id: str, issuer: str, ttl: timedelta = timedelta(hours=1), public_key: str | None = None, trust_score: int = 50) -> WorkloadIdentity:
        now = datetime.now(UTC)
        item = WorkloadIdentity(secrets.token_hex(16), subject, workload_id, issuer, now, now + ttl, max(0, min(100, trust_score)), public_key)
        self._identities[item.id] = item
        return item

    def authenticate(self, identity_id: str, *, workload_id: str, now: datetime | None = None) -> WorkloadIdentity:
        item = self._identities[identity_id]
        now = now or datetime.now(UTC)
        if item.revoked_at or item.workload_id != workload_id or item.expires_at <= now:
            raise PermissionError("workload identity invalid")
        if item.trust_score < 50:
            raise PermissionError("workload trust below threshold")
        return item

    def rotate(self, identity_id: str, ttl: timedelta = timedelta(hours=1)) -> WorkloadIdentity:
        old = self._identities[identity_id]
        new = self.register(old.subject, old.workload_id, old.issuer, ttl, old.public_key, old.trust_score)
        self.revoke(identity_id)
        return new

    def revoke(self, identity_id: str) -> None:
        self._identities[identity_id] = replace(self._identities[identity_id], revoked_at=datetime.now(UTC))

    def bind_secret(self, identity_id: str, secret_id: str) -> tuple[str, str]:
        return identity_id, secret_id

    def bind_capability(self, identity_id: str, capability: str) -> tuple[str, str]:
        return identity_id, capability

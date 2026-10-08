"""Backup, recovery, failover and release-security contracts."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json

@dataclass(frozen=True, slots=True)
class RecoveryTarget:
    rpo_seconds: int
    rto_seconds: int

@dataclass(frozen=True, slots=True)
class BackupManifest:
    backup_id: str
    created_at: str
    digest: str
    provider: str
    encrypted: bool

class ResilienceController:
    def __init__(self, target: RecoveryTarget) -> None:
        self.target = target
        self._backups: dict[str, dict] = {}

    def backup(self, provider: str, payload: dict, encrypted: bool = True) -> BackupManifest:
        raw = json.dumps(payload, sort_keys=True).encode()
        backup_id = hashlib.sha256(raw + datetime.now(UTC).isoformat().encode()).hexdigest()[:24]
        manifest = BackupManifest(backup_id, datetime.now(UTC).isoformat(), hashlib.sha256(raw).hexdigest(), provider, encrypted)
        self._backups[backup_id] = payload
        return manifest

    def restore(self, backup_id: str) -> dict:
        return self._backups[backup_id]

    def failover(self, providers: list[dict]) -> dict:
        for provider in providers:
            if provider.get("healthy"):
                return provider
        raise RuntimeError("no healthy secret provider available")

@dataclass(frozen=True, slots=True)
class ReleaseGate:
    commit: str
    security_checks: tuple[str, ...]
    approved: bool = False

    def verify(self, required: set[str]) -> bool:
        return self.approved and required.issubset(self.security_checks)

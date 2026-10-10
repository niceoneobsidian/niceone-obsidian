"""General credential rotation and revocation lifecycle."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from .manager import SecretManager, SecretMetadata, SecretState


class CredentialStatus(StrEnum):
    ACTIVE = "active"
    EXPIRING = "expiring"
    REVOKED = "revoked"


@dataclass(frozen=True)
class CredentialRecord:
    name: str
    created_at: datetime
    rotated_at: datetime | None
    revoked_at: datetime | None
    status: CredentialStatus


class CredentialLifecycleManager:
    def __init__(self, manager: SecretManager) -> None:
        self._manager = manager
        self._records: dict[str, CredentialRecord] = {}

    def register(self, metadata: SecretMetadata, *, now: datetime | None = None) -> None:
        self._manager.register(metadata)
        timestamp = now or datetime.now(UTC)
        self._records[metadata.name] = CredentialRecord(
            metadata.name, timestamp, None, None, CredentialStatus.ACTIVE
        )

    def rotate(self, name: str, *, value: str | None = None, now: datetime | None = None) -> str:
        metadata = self._manager.metadata(name)
        if metadata is None:
            raise KeyError(f"secret is not registered: {name}")
        if metadata.state is SecretState.REVOKED:
            raise PermissionError(f"secret is revoked: {name}")
        replacement = value or secrets.token_urlsafe(32)
        self._manager.set(name, replacement)
        timestamp = now or datetime.now(UTC)
        previous = self._records.get(name)
        created = previous.created_at if previous else timestamp
        self._records[name] = CredentialRecord(
            name, created, timestamp, None, CredentialStatus.ACTIVE
        )
        return replacement

    def revoke(self, name: str, *, now: datetime | None = None) -> None:
        metadata = self._manager.metadata(name)
        if metadata is None:
            raise KeyError(f"secret is not registered: {name}")
        self._manager.delete(name)
        self._manager.update_metadata(
            SecretMetadata(
                name=metadata.name,
                provider=metadata.provider,
                environment=metadata.environment,
                required=metadata.required,
                scopes=metadata.scopes,
                rotation_days=metadata.rotation_days,
                state=SecretState.REVOKED,
            )
        )
        timestamp = now or datetime.now(UTC)
        previous = self._records.get(name)
        created = previous.created_at if previous else timestamp
        self._records[name] = CredentialRecord(
            name, created, previous.rotated_at if previous else None, timestamp,
            CredentialStatus.REVOKED,
        )

    def status(self, name: str, *, now: datetime | None = None) -> CredentialStatus:
        record = self._records.get(name)
        metadata = self._manager.metadata(name)
        if metadata and metadata.state is SecretState.REVOKED:
            return CredentialStatus.REVOKED
        if not record or not metadata or not metadata.rotation_days:
            return CredentialStatus.ACTIVE
        timestamp = now or datetime.now(UTC)
        anchor = record.rotated_at or record.created_at
        if timestamp >= anchor + timedelta(days=metadata.rotation_days):
            return CredentialStatus.EXPIRING
        return CredentialStatus.ACTIVE

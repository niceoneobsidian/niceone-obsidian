"""Unified credential health and authentication-readiness checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Callable

from .lifecycle import CredentialLifecycleManager, CredentialStatus
from .manager import SecretManager


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    MISSING = "missing"
    REVOKED = "revoked"
    EXPIRING = "expiring"
    INVALID = "invalid"


@dataclass(frozen=True)
class CredentialHealth:
    name: str
    status: HealthStatus
    checked_at: datetime
    provider: str
    reason: str | None = None


class CredentialHealthManager:
    def __init__(
        self,
        manager: SecretManager,
        lifecycle: CredentialLifecycleManager | None = None,
        validators: dict[str, Callable[[str], bool]] | None = None,
    ) -> None:
        self._manager = manager
        self._lifecycle = lifecycle
        self._validators = dict(validators or {})

    def check(self, name: str, *, now: datetime | None = None) -> CredentialHealth:
        checked = now or datetime.now(UTC)
        metadata = self._manager.metadata(name)
        provider = metadata.provider if metadata else "unknown"
        if metadata is None:
            return CredentialHealth(name, HealthStatus.INVALID, checked, provider, "unregistered")
        if self._lifecycle and self._lifecycle.status(name, now=checked) is CredentialStatus.REVOKED:
            return CredentialHealth(name, HealthStatus.REVOKED, checked, provider, "revoked")
        value = self._manager.get(name)
        if not value:
            return CredentialHealth(name, HealthStatus.MISSING, checked, provider, "missing")
        validator = self._validators.get(name)
        if validator and not validator(value):
            return CredentialHealth(
                name, HealthStatus.INVALID, checked, provider, "provider validation failed"
            )
        if self._lifecycle and self._lifecycle.status(name, now=checked) is CredentialStatus.EXPIRING:
            return CredentialHealth(
                name, HealthStatus.EXPIRING, checked, provider, "rotation due"
            )
        return CredentialHealth(name, HealthStatus.HEALTHY, checked, provider)

    def check_all(self) -> dict[str, CredentialHealth]:
        return {name: self.check(name) for name in self._registered_names()}

    def _registered_names(self) -> tuple[str, ...]:
        return self._manager.registered_names()

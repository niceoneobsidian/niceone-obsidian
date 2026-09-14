"""Versioned execution contracts with fail-closed authorization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone


class AuthorizationError(PermissionError):
    """Raised when an execution request is not explicitly authorized."""


@dataclass(frozen=True)
class ExecutionRequest:
    object_id: str
    version: str
    input: Mapping[str, object] = field(default_factory=dict)
    capability: str | None = None
    requested_version: str | None = None
    idempotency_key: str | None = None
    deadline: datetime | None = None
    authorization: Mapping[str, object] | None = None

    def assert_authorized(self) -> None:
        """Require an explicit, capability- and version-matching allow decision."""
        decision = self.authorization
        if not decision or decision.get("decision") != "allow":
            raise AuthorizationError("execution denied: explicit allow decision required")
        if self.capability and decision.get("capability") != self.capability:
            raise AuthorizationError("execution denied: capability mismatch")
        expected = self.requested_version or self.version
        if decision.get("version") not in (expected, "*"):
            raise AuthorizationError("execution denied: version mismatch")
        if not self.idempotency_key:
            raise AuthorizationError("execution denied: idempotency key required")
        if self.deadline is not None:
            deadline = self.deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if deadline <= datetime.now(timezone.utc):
                raise AuthorizationError("execution denied: deadline expired")


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    output: object = None
    error: str | None = None

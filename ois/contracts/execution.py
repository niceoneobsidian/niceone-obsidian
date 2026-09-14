"""Typed contracts for authorization and side-effecting execution."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class AuthorizationDecision(BaseModel):
    """An immutable policy decision required before an external side effect."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: UUID = Field(default_factory=uuid4)
    principal: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    capability_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    decision: Decision
    reason: str = Field(min_length=1)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def expiry_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("authorization expiry must be timezone-aware")
        return value


class ExecutionRequest(BaseModel):
    """The only request shape accepted by a side-effecting executor."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID = Field(default_factory=uuid4)
    principal: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    capability_version: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    authorization: AuthorizationDecision
    deadline: datetime
    idempotency_key: str = Field(min_length=1)

    @field_validator("deadline")
    @classmethod
    def deadline_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("execution deadline must be timezone-aware")
        return value

    def assert_authorized(self, now: datetime | None = None) -> None:
        """Fail closed if identity, capability, decision, or expiry does not match."""
        current = now or datetime.now(timezone.utc)
        if self.authorization.decision is not Decision.ALLOW:
            raise PermissionError("execution requires an allow decision")
        if self.authorization.principal != self.principal:
            raise PermissionError("authorization principal does not match request")
        if self.authorization.capability_id != self.capability_id:
            raise PermissionError("authorization capability does not match request")
        if self.authorization.capability_version != self.capability_version:
            raise PermissionError("authorization capability version does not match request")
        if current >= self.authorization.expires_at:
            raise PermissionError("authorization decision has expired")
        if current >= self.deadline:
            raise TimeoutError("execution deadline has expired")


class ExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    succeeded: bool
    output: Any = None
    error_code: str | None = None
    evidence_id: UUID | None = None

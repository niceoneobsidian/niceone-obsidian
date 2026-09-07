from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class HITLStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class HITLError(ValueError):
    """Base HITL gate error."""


class HITLAuthorizationError(HITLError):
    """Raised when a reviewer lacks the required role."""


class HITLBindingError(HITLError):
    """Raised when approval is not bound to the exact proposed action."""


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class HITLGate:
    gate_id: UUID
    execution_id: UUID
    tenant_id: UUID
    action_type: str
    required_role: str
    proposed_side_effect: dict[str, Any]
    side_effect_hash: str
    plan_hash: str
    expires_at: datetime
    status: HITLStatus = HITLStatus.PENDING
    reviewed_by_user_id: UUID | None = None
    reviewed_at: datetime | None = None
    cryptographic_signature: str | None = None

    @classmethod
    def create(
        cls,
        *,
        gate_id: UUID,
        execution_id: UUID,
        tenant_id: UUID,
        action_type: str,
        required_role: str,
        proposed_side_effect: dict[str, Any],
        plan_hash: str,
        expires_at: datetime,
    ) -> HITLGate:
        return cls(
            gate_id=gate_id,
            execution_id=execution_id,
            tenant_id=tenant_id,
            action_type=action_type,
            required_role=required_role,
            proposed_side_effect=proposed_side_effect,
            side_effect_hash=canonical_hash(proposed_side_effect),
            plan_hash=plan_hash,
            expires_at=expires_at,
        )

    def resolve(
        self,
        *,
        tenant_id: UUID,
        execution_id: UUID,
        action_type: str,
        plan_hash: str,
        reviewer_id: UUID,
        reviewer_roles: set[str],
        decision: HITLStatus,
        attestation_key: bytes | None = None,
        now: datetime | None = None,
    ) -> HITLGate:
        now = now or datetime.now(UTC)
        if self.status is not HITLStatus.PENDING:
            raise HITLError("HITL gate is already resolved")
        if now >= self.expires_at:
            return self._transition(HITLStatus.EXPIRED, now=now)
        if tenant_id != self.tenant_id or execution_id != self.execution_id:
            raise HITLBindingError("tenant or execution binding mismatch")
        if action_type != self.action_type or plan_hash != self.plan_hash:
            raise HITLBindingError("action or plan binding mismatch")
        if self.required_role not in reviewer_roles:
            raise HITLAuthorizationError("reviewer lacks required role")
        if decision not in {HITLStatus.APPROVED, HITLStatus.REJECTED}:
            raise HITLError("resolution must be APPROVED or REJECTED")

        signature = None
        if attestation_key is not None:
            message = self._attestation_message(decision=decision, reviewer_id=reviewer_id)
            signature = hmac.new(attestation_key, message, hashlib.sha256).hexdigest()

        return self._transition(
            decision,
            now=now,
            reviewer_id=reviewer_id,
            signature=signature,
        )

    def verify_side_effect(self, proposed_side_effect: dict[str, Any]) -> None:
        """Fail closed if the action changed after approval."""
        if canonical_hash(proposed_side_effect) != self.side_effect_hash:
            raise HITLBindingError("side-effect payload integrity check failed")

    def _attestation_message(self, *, decision: HITLStatus, reviewer_id: UUID) -> bytes:
        return (
            f"{self.tenant_id}:{self.execution_id}:{self.gate_id}:"
            f"{self.action_type}:{self.plan_hash}:{self.side_effect_hash}:"
            f"{reviewer_id}:{decision.value}"
        ).encode("utf-8")

    def _transition(
        self,
        status: HITLStatus,
        *,
        now: datetime,
        reviewer_id: UUID | None = None,
        signature: str | None = None,
    ) -> HITLGate:
        return HITLGate(
            gate_id=self.gate_id,
            execution_id=self.execution_id,
            tenant_id=self.tenant_id,
            action_type=self.action_type,
            required_role=self.required_role,
            proposed_side_effect=self.proposed_side_effect,
            side_effect_hash=self.side_effect_hash,
            plan_hash=self.plan_hash,
            expires_at=self.expires_at,
            status=status,
            reviewed_by_user_id=reviewer_id,
            reviewed_at=now,
            cryptographic_signature=signature,
        )

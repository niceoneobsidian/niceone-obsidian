from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID, uuid4

from .types import ExecutionStatus, FailureClass, RiskLevel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ExecutionIdentity:
    execution_id: UUID = field(default_factory=uuid4)
    tenant_id: str = "default"
    workflow_id: str | None = None
    workflow_version: str | None = None


@dataclass
class ExecutionContext:
    identity: ExecutionIdentity
    objective: str
    constraints: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    status: ExecutionStatus = ExecutionStatus.RECEIVED
    risk_level: RiskLevel = RiskLevel.LOW

    intent: Mapping[str, Any] | None = None
    plan: Mapping[str, Any] | None = None
    current_node: str | None = None

    working_memory: dict[str, Any] = field(default_factory=dict)
    retrieved_context: list[Mapping[str, Any]] = field(default_factory=list)
    artifacts: list[Mapping[str, Any]] = field(default_factory=list)

    approvals: list[Mapping[str, Any]] = field(default_factory=list)
    escalations: list[Mapping[str, Any]] = field(default_factory=list)

    observations: list[Mapping[str, Any]] = field(default_factory=list)
    validation_results: list[Mapping[str, Any]] = field(default_factory=list)

    retry_count: int = 0
    recovery_attempts: int = 0

    last_failure: FailureClass | None = None
    error: Mapping[str, Any] | None = None

    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def touch(self) -> None:
        self.updated_at = utc_now()

    def set_status(self, status: ExecutionStatus) -> None:
        if self.status in {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.STOPPED,
            ExecutionStatus.ESCALATED,
        }:
            raise ValueError(
                f"Terminal execution status "
                f"{self.status.value} cannot transition to "
                f"{status.value}."
            )

        self.status = status
        self.touch()


# ------------------------------------------------------------------
# Durable checkpoint reconstruction
# ------------------------------------------------------------------

def _execution_context_from_dict(cls, payload):
    """
    Reconstruct ExecutionContext from a durable checkpoint payload.

    Kept as a compatibility layer so the existing state model does not
    need to change its public construction semantics.
    """
    from dataclasses import fields

    identity_payload = payload.get("identity", {})
    from uuid import UUID

    raw_execution_id = identity_payload.get("execution_id")

    if raw_execution_id is not None:
        try:
            raw_execution_id = UUID(str(raw_execution_id))
        except (TypeError, ValueError):
            pass

    identity = ExecutionIdentity(
        tenant_id=identity_payload.get("tenant_id", ""),
        execution_id=raw_execution_id,
    )

    context = cls(
        identity=identity,
        objective=payload.get("objective", ""),
    )

    for field_name in fields(context):
        name = field_name.name

        if name in {"identity", "objective"}:
            continue

        if name not in payload:
            continue

        value = payload[name]

        current = getattr(context, name, None)

        if hasattr(current, "__class__") and hasattr(current.__class__, "__members__"):
            try:
                value = current.__class__(value)
            except Exception:
                pass

        try:
            setattr(context, name, value)
        except Exception:
            pass

    return context


if not hasattr(ExecutionContext, "from_dict"):
    ExecutionContext.from_dict = classmethod(_execution_context_from_dict)

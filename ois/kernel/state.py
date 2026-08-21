from __future__ import annotations

from dataclasses import dataclass, field, fields
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

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExecutionContext":
        """Reconstruct an execution context from a durable checkpoint payload."""
        identity_payload = payload.get("identity", {})
        if not isinstance(identity_payload, Mapping):
            identity_payload = {}

        raw_execution_id = identity_payload.get("execution_id")
        execution_id = uuid4()
        if raw_execution_id is not None:
            try:
                execution_id = UUID(str(raw_execution_id))
            except (TypeError, ValueError):
                pass

        identity = ExecutionIdentity(
            tenant_id=str(identity_payload.get("tenant_id", "default")),
            execution_id=execution_id,
            workflow_id=identity_payload.get("workflow_id"),
            workflow_version=identity_payload.get("workflow_version"),
        )

        context = cls(
            identity=identity,
            objective=str(payload.get("objective", "")),
        )

        for field_info in fields(context):
            name = field_info.name
            if name in {"identity", "objective"} or name not in payload:
                continue

            value = payload[name]
            current = getattr(context, name, None)
            if isinstance(current, (ExecutionStatus, FailureClass, RiskLevel)):
                try:
                    value = type(current)(value)
                except (TypeError, ValueError):
                    continue

            try:
                setattr(context, name, value)
            except (AttributeError, TypeError):
                continue

        return context

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from .types import ExecutionStatus, FailureClass, RiskLevel


def utc_now() -> datetime:
    return datetime.now(UTC)


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
    metadata: dict[str, Any] = field(default_factory=dict)

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
                f"Terminal execution status {self.status.value} cannot transition to {status.value}."
            )
        self.status = status
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-compatible checkpoint representation."""
        return {
            "identity": {
                "execution_id": str(self.identity.execution_id),
                "tenant_id": self.identity.tenant_id,
                "workflow_id": self.identity.workflow_id,
                "workflow_version": self.identity.workflow_version,
            },
            "objective": self.objective,
            "constraints": dict(self.constraints),
            "metadata": dict(self.metadata),
            "status": self.status.value,
            "risk_level": self.risk_level.value,
            "intent": dict(self.intent) if self.intent is not None else None,
            "plan": dict(self.plan) if self.plan is not None else None,
            "current_node": self.current_node,
            "working_memory": dict(self.working_memory),
            "retrieved_context": [dict(item) for item in self.retrieved_context],
            "artifacts": [dict(item) for item in self.artifacts],
            "approvals": [dict(item) for item in self.approvals],
            "escalations": [dict(item) for item in self.escalations],
            "observations": [dict(item) for item in self.observations],
            "validation_results": [dict(item) for item in self.validation_results],
            "retry_count": self.retry_count,
            "recovery_attempts": self.recovery_attempts,
            "last_failure": self.last_failure.value if self.last_failure else None,
            "error": dict(self.error) if self.error is not None else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ExecutionContext:
        """Reconstruct an execution context from a durable checkpoint payload."""
        identity_payload = payload.get("identity", {})
        if not isinstance(identity_payload, Mapping):
            identity_payload = {}

        raw_execution_id = identity_payload.get("execution_id")
        execution_id = uuid4()
        if raw_execution_id is not None:
            with suppress(TypeError, ValueError):
                execution_id = UUID(str(raw_execution_id))

        identity = ExecutionIdentity(
            tenant_id=str(identity_payload.get("tenant_id", "default")),
            execution_id=execution_id,
            workflow_id=identity_payload.get("workflow_id"),
            workflow_version=identity_payload.get("workflow_version"),
        )
        context = cls(identity=identity, objective=str(payload.get("objective", "")))

        for field_info in fields(context):
            name = field_info.name
            if name in {"identity", "objective"} or name not in payload:
                continue
            value = payload[name]
            current = getattr(context, name, None)
            if isinstance(current, ExecutionStatus | FailureClass | RiskLevel):
                with suppress(TypeError, ValueError):
                    value = type(current)(value)
                if not isinstance(value, type(current)):
                    continue
            if name in {"created_at", "updated_at"} and isinstance(value, str):
                with suppress(TypeError, ValueError):
                    value = datetime.fromisoformat(value)
            with suppress(AttributeError, TypeError):
                setattr(context, name, value)
        return context

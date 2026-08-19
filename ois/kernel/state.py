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
        }:
            raise ValueError(
                f"Terminal execution status "
                f"{self.status.value} cannot transition to "
                f"{status.value}."
            )

        self.status = status
        self.touch()

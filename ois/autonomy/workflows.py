"""Source-triggered workflow definitions and lifecycle."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

from .events import EventEnvelope


class WorkflowStatus(StrEnum):
    ENABLED = "enabled"
    PAUSED = "paused"
    DISABLED = "disabled"


@dataclass(frozen=True)
class WorkflowTrigger:
    event_type: str
    source_id: str | None = None
    conditions: Mapping[str, object] = field(default_factory=dict)

    def matches(self, event: EventEnvelope) -> bool:
        if event.event_type != self.event_type:
            return False
        if self.source_id is not None and self.source_id != event.source_id:
            return False
        return all(event.payload.get(key) == value for key, value in self.conditions.items())


WorkflowAction = Callable[[EventEnvelope], object]


@dataclass
class SourceWorkflow:
    workflow_id: str
    version: str
    tenant_id: str
    workspace_id: str
    trigger: WorkflowTrigger
    action: WorkflowAction
    status: WorkflowStatus = WorkflowStatus.ENABLED
    metadata: Mapping[str, object] = field(default_factory=dict)

    def matches(self, event: EventEnvelope) -> bool:
        return (
            self.status == WorkflowStatus.ENABLED
            and event.tenant_id == self.tenant_id
            and event.workspace_id == self.workspace_id
            and self.trigger.matches(event)
        )


@dataclass(frozen=True)
class WorkflowRun:
    run_id: str
    workflow_id: str
    workflow_version: str
    event_id: str
    status: WorkflowStatus | str
    result: Any = None
    error: Mapping[str, object] | None = None

    @classmethod
    def success(cls, workflow: SourceWorkflow, event: EventEnvelope, result: object) -> "WorkflowRun":
        return cls(str(uuid4()), workflow.workflow_id, workflow.version, event.event_id, "completed", result=result)

    @classmethod
    def failure(cls, workflow: SourceWorkflow, event: EventEnvelope, error: Exception) -> "WorkflowRun":
        return cls(
            str(uuid4()),
            workflow.workflow_id,
            workflow.version,
            event.event_id,
            "failed",
            error={"type": type(error).__name__, "message": str(error)},
        )

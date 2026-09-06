from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class TaskStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class PlanError(Exception):
    """Base planning error."""


class DuplicateTaskError(PlanError):
    """Raised when a task identifier is duplicated."""


class UnknownDependencyError(PlanError):
    """Raised when a task references an unknown dependency."""


class CyclicPlanError(PlanError):
    """Raised when a plan contains a dependency cycle."""


@dataclass
class TaskNode:
    task_id: str
    capability_id: str
    capability_version: str
    input_data: Mapping[str, Any] = field(default_factory=dict)
    dependencies: tuple[str, ...] = ()
    status: TaskStatus = TaskStatus.PENDING
    output: Any = None
    error: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "capability_id": self.capability_id,
            "capability_version": self.capability_version,
            "input_data": dict(self.input_data),
            "dependencies": list(self.dependencies),
            "status": self.status.value,
            "output": self.output,
            "error": dict(self.error) if self.error is not None else None,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TaskNode:
        return cls(
            task_id=str(payload["task_id"]),
            capability_id=str(payload["capability_id"]),
            capability_version=str(payload["capability_version"]),
            input_data=payload.get("input_data", {}),
            dependencies=tuple(payload.get("dependencies", ())),
            status=TaskStatus(payload.get("status", TaskStatus.PENDING.value)),
            output=payload.get("output"),
            error=payload.get("error"),
            metadata=payload.get("metadata", {}),
        )


@dataclass
class ExecutionPlan:
    plan_id: str = field(default_factory=lambda: str(uuid4()))
    version: str = "1.0.0"
    objective: str = ""
    tasks: dict[str, TaskNode] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def add_task(self, task: TaskNode) -> None:
        if task.task_id in self.tasks:
            raise DuplicateTaskError(f"Task already exists: {task.task_id}")
        self.tasks[task.task_id] = task

    def validate(self) -> None:
        self._validate_dependencies()
        self._validate_cycles()

    def _validate_dependencies(self) -> None:
        for task in self.tasks.values():
            for dependency in task.dependencies:
                if dependency not in self.tasks:
                    raise UnknownDependencyError(f"Task {task.task_id} depends on unknown task {dependency}")

    def _validate_cycles(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise CyclicPlanError(f"Dependency cycle detected at {task_id}")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dependency in self.tasks[task_id].dependencies:
                visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in self.tasks:
            visit(task_id)

    def ready_tasks(self) -> list[TaskNode]:
        ready: list[TaskNode] = []
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            if all(self.tasks[dependency].status == TaskStatus.SUCCEEDED for dependency in task.dependencies):
                task.status = TaskStatus.READY
                ready.append(task)
        return ready

    def is_complete(self) -> bool:
        return all(task.status in {TaskStatus.SUCCEEDED, TaskStatus.SKIPPED} for task in self.tasks.values())

    def has_failed(self) -> bool:
        return any(task.status == TaskStatus.FAILED for task in self.tasks.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "version": self.version,
            "objective": self.objective,
            "tasks": {task_id: task.to_dict() for task_id, task in self.tasks.items()},
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ExecutionPlan:
        tasks_payload = payload.get("tasks", {})
        plan = cls(
            plan_id=str(payload.get("plan_id", uuid4())),
            version=str(payload.get("version", "1.0.0")),
            objective=str(payload.get("objective", "")),
            metadata=payload.get("metadata", {}),
        )
        for task_id, task_payload in tasks_payload.items():
            task = TaskNode.from_dict(task_payload)
            if task.task_id != task_id:
                raise PlanError("Checkpoint task key does not match task_id")
            plan.add_task(task)
        plan.validate()
        return plan

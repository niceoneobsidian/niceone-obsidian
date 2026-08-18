from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


class TaskStatus(str, Enum):
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


@dataclass
class ExecutionPlan:
    plan_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    version: str = "1.0.0"

    objective: str = ""

    tasks: dict[str, TaskNode] = field(
        default_factory=dict
    )

    metadata: Mapping[str, Any] = field(
        default_factory=dict
    )

    def add_task(self, task: TaskNode) -> None:
        if task.task_id in self.tasks:
            raise DuplicateTaskError(
                f"Task already exists: {task.task_id}"
            )

        self.tasks[task.task_id] = task

    def validate(self) -> None:
        self._validate_dependencies()
        self._validate_cycles()

    def _validate_dependencies(self) -> None:
        for task in self.tasks.values():
            for dependency in task.dependencies:
                if dependency not in self.tasks:
                    raise UnknownDependencyError(
                        f"Task {task.task_id} depends on "
                        f"unknown task {dependency}"
                    )

    def _validate_cycles(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise CyclicPlanError(
                    f"Dependency cycle detected at {task_id}"
                )

            if task_id in visited:
                return

            visiting.add(task_id)

            for dependency in self.tasks[
                task_id
            ].dependencies:
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

            if all(
                self.tasks[dependency].status
                == TaskStatus.SUCCEEDED
                for dependency in task.dependencies
            ):
                task.status = TaskStatus.READY
                ready.append(task)

        return ready

    def is_complete(self) -> bool:
        return all(
            task.status
            in {
                TaskStatus.SUCCEEDED,
                TaskStatus.SKIPPED,
            }
            for task in self.tasks.values()
        )

    def has_failed(self) -> bool:
        return any(
            task.status == TaskStatus.FAILED
            for task in self.tasks.values()
        )

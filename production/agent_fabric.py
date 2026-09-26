"""Governed multi-agent execution fabric using the canonical Supervisor and AgentRegistry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ois.kernel import AgentRegistry, ExecutionContext, Supervisor


@dataclass(frozen=True)
class AgentTask:
    capability_id: str
    version: str
    input_data: dict[str, Any]


@dataclass(frozen=True)
class AgentFabricResult:
    task_results: tuple[Any, ...]
    completed: bool
    failed_index: int | None = None


class AgentFabric:
    """Bounded sequential delegation; each task is resolved and authorized by Supervisor."""

    def __init__(self, supervisor: Supervisor, registry: AgentRegistry) -> None:
        self.supervisor = supervisor
        self.registry = registry

    def validate(self, tasks: tuple[AgentTask, ...]) -> None:
        if not tasks:
            raise ValueError("agent fabric requires at least one task")
        for task in tasks:
            self.registry.resolve(task.capability_id, task.version)

    def execute(self, tasks: tuple[AgentTask, ...], context: ExecutionContext) -> AgentFabricResult:
        self.validate(tasks)
        results: list[Any] = []
        for index, task in enumerate(tasks):
            invocation_id = f"{context.identity.execution_id}:agent:{index}"
            self.supervisor.select_agent(
                task.capability_id,
                task.version,
                context=context,
                input_data=task.input_data,
                invocation_id=invocation_id,
            )
            result = self.supervisor.execute(
                context=context,
                objective=context.objective,
                capability_id=task.capability_id,
                version=task.version,
                input_data=task.input_data,
                invocation_id=f"{context.identity.execution_id}:invoke:{index}",
            )
            results.append(result)
            status = getattr(result, "status", None)
            if getattr(status, "value", status) not in {"success", "succeeded", "completed"}:
                return AgentFabricResult(tuple(results), False, index)
        return AgentFabricResult(tuple(results), True)

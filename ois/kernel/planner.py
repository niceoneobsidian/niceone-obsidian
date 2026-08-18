from __future__ import annotations

from typing import Any, Mapping

from .planning import ExecutionPlan, TaskNode


class PlanBuilder:
    """
    Deterministic plan builder.

    This does not use an LLM. It creates an explicit execution graph from
    structured task definitions. An intelligent planner can later target
    this interface.
    """

    def __init__(self, objective: str) -> None:
        self._plan = ExecutionPlan(
            objective=objective
        )

    def task(
        self,
        task_id: str,
        capability_id: str,
        capability_version: str,
        input_data: Mapping[str, Any] | None = None,
        dependencies: tuple[str, ...] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> "PlanBuilder":
        self._plan.add_task(
            TaskNode(
                task_id=task_id,
                capability_id=capability_id,
                capability_version=capability_version,
                input_data=input_data or {},
                dependencies=dependencies,
                metadata=metadata or {},
            )
        )

        return self

    def build(self) -> ExecutionPlan:
        self._plan.validate()
        return self._plan

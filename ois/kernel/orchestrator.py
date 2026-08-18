from __future__ import annotations

from .planning import ExecutionPlan, TaskStatus
from .runtime import ExecutionRuntime
from .state import ExecutionContext


class OrchestrationError(Exception):
    """Base orchestration error."""


class PlanExecutionError(OrchestrationError):
    """Raised when plan execution cannot continue."""


class PlanOrchestrator:
    """
    Deterministic DAG orchestrator.

    Runtime owns individual capability execution.
    Orchestrator owns plan-level lifecycle.
    """

    def __init__(
        self,
        runtime: ExecutionRuntime,
    ) -> None:
        self.runtime = runtime

    def execute(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext,
    ) -> ExecutionPlan:

        plan.validate()

        while not plan.is_complete():

            ready = plan.ready_tasks()

            if not ready:
                if plan.has_failed():
                    raise PlanExecutionError(
                        "Plan contains failed tasks "
                        "and cannot continue."
                    )

                raise PlanExecutionError(
                    "No executable tasks remain. "
                    "The plan may be blocked."
                )

            for task in ready:

                task.status = TaskStatus.RUNNING

                context.current_node = (
                    task.task_id
                )

                try:

                    result = self.runtime.execute(
                        context=context,
                        capability_id=(
                            task.capability_id
                        ),
                        version=(
                            task.capability_version
                        ),
                        input_data=dict(
                            task.input_data
                        ),
                    )

                    if (
                        result.status
                        != result.status.SUCCEEDED
                    ):
                        task.status = (
                            TaskStatus.FAILED
                        )

                        task.error = (
                            result.error
                        )

                        return plan

                    task.output = result.output

                    task.status = (
                        TaskStatus.SUCCEEDED
                    )

                except Exception as exc:

                    task.status = (
                        TaskStatus.FAILED
                    )

                    task.error = {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }

                    return plan

        # The graph is now completely executed.
        self.runtime.complete(context)

        return plan

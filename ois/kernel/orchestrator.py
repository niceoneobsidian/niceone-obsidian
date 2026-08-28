from __future__ import annotations

from .planning import ExecutionPlan, TaskStatus
from .runtime import ExecutionRuntime
from .state import ExecutionContext
from .types import FailureClass, InvocationStatus


class OrchestrationError(Exception):
    """Base orchestration error."""


class PlanExecutionError(OrchestrationError):
    """Raised when plan execution cannot continue."""


class PlanOrchestrator:
    """Deterministic DAG orchestrator with bounded recovery."""

    def __init__(self, runtime: ExecutionRuntime) -> None:
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
                        "Plan contains failed tasks and cannot continue."
                    )
                raise PlanExecutionError(
                    "No executable tasks remain. The plan may be blocked."
                )

            for task in ready:
                task.status = TaskStatus.RUNNING
                context.current_node = task.task_id
                invocation_id = f"{context.identity.execution_id}:{task.task_id}"

                result = self.runtime.execute(
                    context=context,
                    capability_id=task.capability_id,
                    version=task.capability_version,
                    input_data=dict(task.input_data),
                    invocation_id=invocation_id,
                )

                if result.status == InvocationStatus.SUCCEEDED:
                    task.output = result.output
                    task.error = None
                    task.status = TaskStatus.SUCCEEDED
                    continue

                task.status = TaskStatus.FAILED
                task.error = result.error
                failure_name = (result.error or {}).get("failure_class", "unknown")
                try:
                    failure = FailureClass(failure_name)
                except ValueError:
                    failure = FailureClass.UNKNOWN

                decision = self.runtime.recovery.apply(context, failure)
                self.runtime.evidence.record(
                    context.identity.execution_id,
                    "execution.recovery_decision",
                    {
                        "task_id": task.task_id,
                        "invocation_id": invocation_id,
                        "failure_class": failure.value,
                        "action": decision.action,
                        "retry_allowed": decision.retry_allowed,
                        "terminal": decision.terminal,
                    },
                )
                self.runtime.checkpoint_store.save(context)

                if decision.action == "retry":
                    task.status = TaskStatus.PENDING
                    task.error = None
                    continue

                raise PlanExecutionError(
                    f"Task {task.task_id} failed: "
                    f"{(result.error or {}).get('message', 'unknown failure')}"
                )

        self.runtime.complete(context)
        return plan

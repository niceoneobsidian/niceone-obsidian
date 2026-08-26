from __future__ import annotations

from uuid import UUID

from .checkpoint import CheckpointStore
from .planning import ExecutionPlan, TaskStatus
from .runtime import ExecutionRuntime
from .state import ExecutionContext
from .types import InvocationStatus


class OrchestrationError(Exception):
    """Base orchestration error."""


class PlanExecutionError(OrchestrationError):
    """Raised when plan execution cannot continue."""


class PlanOrchestrator:
    """Deterministic DAG orchestrator with checkpoint/resume semantics."""

    def __init__(self, runtime: ExecutionRuntime) -> None:
        self.runtime = runtime

    def execute(self, plan: ExecutionPlan, context: ExecutionContext) -> ExecutionPlan:
        plan.validate()
        context.plan = plan.to_dict()
        self.runtime.checkpoint_store.save(context)

        self._normalize_interrupted_tasks(plan)

        while not plan.is_complete():
            ready = plan.ready_tasks()

            if not ready:
                if plan.has_failed():
                    raise PlanExecutionError("Plan contains failed tasks and cannot continue.")
                raise PlanExecutionError("No executable tasks remain. The plan may be blocked.")

            for task in ready:
                task.status = TaskStatus.RUNNING
                context.current_node = task.task_id
                context.plan = plan.to_dict()
                self.runtime.checkpoint_store.save(context)

                try:
                    invocation_id = f"{context.identity.execution_id}:{task.task_id}"
                    result = self.runtime.execute(
                        context=context,
                        capability_id=task.capability_id,
                        version=task.capability_version,
                        input_data=dict(task.input_data),
                        invocation_id=invocation_id,
                    )

                    if result.status != InvocationStatus.SUCCEEDED:
                        task.status = TaskStatus.FAILED
                        task.error = result.error
                        context.plan = plan.to_dict()
                        self.runtime.checkpoint_store.save(context)
                        return plan

                    task.output = result.output
                    task.status = TaskStatus.SUCCEEDED
                    context.plan = plan.to_dict()
                    self.runtime.checkpoint_store.save(context)

                except Exception as exc:
                    task.status = TaskStatus.FAILED
                    task.error = {"type": type(exc).__name__, "message": str(exc)}
                    context.plan = plan.to_dict()
                    self.runtime.checkpoint_store.save(context)
                    return plan

        self.runtime.complete(context)
        return plan

    def resume(self, execution_id: UUID) -> tuple[ExecutionPlan, ExecutionContext]:
        """Restore a checkpointed execution and continue its persisted plan."""
        context = self.runtime.checkpoint_store.load(execution_id)
        if context.plan is None:
            raise PlanExecutionError("Checkpoint does not contain a resumable execution plan.")
        plan = ExecutionPlan.from_dict(context.plan)
        self._normalize_interrupted_tasks(plan)
        resumed = self.execute(plan, context)
        return resumed, context

    @staticmethod
    def _normalize_interrupted_tasks(plan: ExecutionPlan) -> None:
        """Turn a worker-crash RUNNING marker into resumable work.

        Completed tasks remain SUCCEEDED and are never replayed. A task left
        RUNNING at crash time is safe to revisit because its stable invocation
        identity is checked against the durable idempotency store.
        """
        for task in plan.tasks.values():
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.PENDING

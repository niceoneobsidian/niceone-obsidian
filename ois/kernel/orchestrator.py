from __future__ import annotations

from .planning import ExecutionPlan, TaskStatus
from .postgres import ExecutionLease, PostgreSQLExecutionCoordinator
from .runtime import ExecutionRuntime
from .state import ExecutionContext
from .types import FailureClass, InvocationStatus


class OrchestrationError(Exception):
    """Base orchestration error."""


class PlanExecutionError(OrchestrationError):
    """Raised when plan execution cannot continue."""


class PlanOrchestrator:
    """Deterministic DAG orchestrator with bounded recovery and optional fencing."""

    def __init__(self, runtime: ExecutionRuntime,
                 coordinator: PostgreSQLExecutionCoordinator | None = None) -> None:
        self.runtime = runtime
        self.coordinator = coordinator

    def execute(self, plan: ExecutionPlan, context: ExecutionContext,
                *, worker_id: str | None = None,
                lease: ExecutionLease | None = None) -> ExecutionPlan:
        plan.validate()
        owned_lease = lease
        release_when_done = False
        if self.coordinator is not None and owned_lease is None:
            if not worker_id:
                raise PlanExecutionError("worker_id is required for fenced execution")
            owned_lease = self.coordinator.claim(
                context.identity.execution_id,
                context.identity.tenant_id,
                worker_id,
            )
            release_when_done = True
        if owned_lease is not None and self.runtime.coordinator is None:
            raise PlanExecutionError("runtime must be configured with the execution coordinator")

        try:
            self._checkpoint(context, owned_lease)
            while not plan.is_complete():
                self._assert_lease(owned_lease)
                ready = plan.ready_tasks()
                if not ready:
                    if plan.has_failed():
                        raise PlanExecutionError("Plan contains failed tasks and cannot continue.")
                    raise PlanExecutionError("No executable tasks remain. The plan may be blocked.")

                for task in ready:
                    self._assert_lease(owned_lease)
                    task.status = TaskStatus.RUNNING
                    context.current_node = task.task_id
                    context.plan = plan.to_dict()
                    self._checkpoint(context, owned_lease)
                    invocation_id = f"{context.identity.execution_id}:{task.task_id}"
                    result = self.runtime.execute(
                        context=context,
                        capability_id=task.capability_id,
                        version=task.capability_version,
                        input_data=dict(task.input_data),
                        invocation_id=invocation_id,
                        lease=owned_lease,
                    )

                    if result.status == InvocationStatus.SUCCEEDED:
                        task.output = result.output
                        task.error = None
                        task.status = TaskStatus.SUCCEEDED
                        context.plan = plan.to_dict()
                        self._checkpoint(context, owned_lease)
                        continue

                    task.status = TaskStatus.FAILED
                    task.error = result.error
                    failure_name = (result.error or {}).get("failure_class", "unknown")
                    try:
                        failure = FailureClass(failure_name)
                    except ValueError:
                        failure = FailureClass.UNKNOWN
                    self.runtime.evidence.record(
                        context.identity.execution_id,
                        "execution.failure",
                        {"task_id": task.task_id, "invocation_id": invocation_id,
                         "failure_class": failure.value, "error": dict(result.error or {})},
                    )
                    decision = self.runtime.recovery.apply(context, failure)
                    self.runtime.evidence.record(
                        context.identity.execution_id,
                        "execution.recovery_decision",
                        {"task_id": task.task_id, "invocation_id": invocation_id,
                         "failure_class": failure.value, "action": decision.action,
                         "retry_allowed": decision.retry_allowed, "terminal": decision.terminal},
                    )
                    context.plan = plan.to_dict()
                    self._checkpoint(context, owned_lease)
                    if decision.action == "retry":
                        task.status = TaskStatus.PENDING
                        task.error = None
                        continue
                    raise PlanExecutionError(
                        f"Task {task.task_id} failed: "
                        f"{(result.error or {}).get('message', 'unknown failure')}"
                    )

            self.runtime.complete(context, lease=owned_lease)
            return plan
        finally:
            if release_when_done and owned_lease is not None:
                self.coordinator.release(owned_lease)

    def _assert_lease(self, lease: ExecutionLease | None) -> None:
        if lease is not None:
            if self.coordinator is None:
                raise PlanExecutionError("lease supplied without coordinator")
            self.coordinator.assert_current(lease)

    def _checkpoint(self, context: ExecutionContext, lease: ExecutionLease | None) -> None:
        self._assert_lease(lease)
        self.runtime.checkpoint_store.save(context)

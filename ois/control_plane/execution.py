"""Integrated P0 control-plane to Kernel execution seam."""

from __future__ import annotations

from collections.abc import Mapping

from ois.kernel import (
    ExecutionContext,
    ExecutionIdentity,
    ExecutionPlan,
    ExecutionRuntime,
    FailureClass,
    PlanBuilder,
    PlanOrchestrator,
    RecoveryPolicy,
    TaskStatus,
)

from .controller import ControlPlane
from .request import ControlRequest


class IntegratedExecution:
    """Submit a registered capability through the authoritative Kernel.

    A capability failure that returns a classified, non-exceptional
    FAILED InvocationResult (as opposed to raising) does not pass through
    ExecutionRuntime's exception-handling recovery path. This integration
    seam is the governed place to apply bounded recovery for that case,
    using the same RecoveryPolicy contract, with an explicit evidence trail.
    """

    def __init__(
        self,
        control_plane: ControlPlane,
        runtime: ExecutionRuntime,
        *,
        recovery: RecoveryPolicy | None = None,
    ) -> None:
        self.control_plane = control_plane
        self.runtime = runtime
        self.orchestrator = PlanOrchestrator(runtime)
        self.recovery = recovery or RecoveryPolicy()

    def build_single_capability_plan(
        self,
        *,
        objective: str,
        request: ControlRequest,
    ) -> ExecutionPlan:
        # Resolution happens before a plan is admitted, while authorization
        # remains authoritative inside the Kernel runtime.
        self.control_plane.resolve_capability(request)
        return (
            PlanBuilder(objective)
            .task(
                task_id="primary",
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                input_data=request.input,
            )
            .build()
        )

    def execute(
        self,
        *,
        objective: str,
        request: ControlRequest,
        tenant_id: str = "default",
        metadata: Mapping[str, object] | None = None,
    ) -> ExecutionContext:
        plan = self.build_single_capability_plan(
            objective=objective,
            request=request,
        )
        context = ExecutionContext(
            identity=ExecutionIdentity(
                tenant_id=tenant_id,
                workflow_id="p0-integrated-spine",
                workflow_version="1.0.0",
            ),
            objective=objective,
            metadata=dict(metadata or {}),
            plan={"plan_id": plan.plan_id, "version": plan.version},
        )

        while True:
            self.orchestrator.execute(plan, context)

            if plan.is_complete():
                return context

            if not plan.has_failed():
                # No ready tasks and nothing failed: the plan is blocked.
                # Surface the context as-is rather than looping forever.
                return context

            failed_task = next(
                (task for task in plan.tasks.values() if task.status == TaskStatus.FAILED),
                None,
            )
            if failed_task is None:
                return context

            raw_failure_class = (failed_task.error or {}).get("failure_class")
            try:
                failure_class = FailureClass(raw_failure_class)
            except ValueError:
                failure_class = FailureClass.UNKNOWN

            decision = self.recovery.apply(context, failure_class)
            self.runtime.evidence.record(
                context.identity.execution_id,
                "execution.recovery_decision",
                {
                    "task_id": failed_task.task_id,
                    "capability_id": failed_task.capability_id,
                    "action": decision.action,
                    "reason": decision.reason,
                },
            )
            self.runtime.checkpoint_store.save(context)

            if decision.action != "retry":
                return context

            # Bounded retry: clear the failed task so ready_tasks() picks
            # it up again on the next orchestrator.execute() call. The
            # invocation_id stays deterministic (same task_id), and since
            # only SUCCEEDED/CANCELLED results are idempotency-cached, the
            # retry safely re-invokes the capability rather than replaying
            # a cached failure.
            failed_task.status = TaskStatus.PENDING
            failed_task.error = None
            failed_task.output = None

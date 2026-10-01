"""Integrated P0 control-plane to Kernel execution seam."""

from __future__ import annotations

from collections.abc import Mapping

from ois.kernel import (
    ExecutionContext,
    ExecutionIdentity,
    ExecutionPlan,
    ExecutionRuntime,
    ExecutionStatus,
    FailureClass,
    PlanBuilder,
    PlanOrchestrator,
    RecoveryPolicy,
    TaskStatus,
)
from ois.supervisor.supervisor import SupervisionAction, SupervisionRequest, Supervisor

from .controller import ControlPlane
from .request import ControlRequest


class IntegratedExecution:
    """Submit a registered capability through the authoritative Kernel.

    Recovery is explicit and bounded. The Supervisor chooses the next safe
    action; the Kernel remains authoritative for policy and execution.
    """

    def __init__(
        self,
        control_plane: ControlPlane,
        runtime: ExecutionRuntime,
        *,
        recovery: RecoveryPolicy | None = None,
        supervisor: Supervisor | None = None,
    ) -> None:
        self.control_plane = control_plane
        self.runtime = runtime
        self.orchestrator = PlanOrchestrator(runtime)
        self.recovery = recovery or RecoveryPolicy()
        self.supervisor = supervisor or Supervisor()

    def build_single_capability_plan(
        self,
        *,
        objective: str,
        request: ControlRequest,
    ) -> ExecutionPlan:
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
        plan = self.build_single_capability_plan(objective=objective, request=request)
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
                self.supervisor.decide(
                    SupervisionRequest(
                        objective=objective,
                        plan_validated=True,
                        authorized=True,
                        status="completed",
                    )
                )
                return context

            if not plan.has_failed():
                return context

            failed_task = next(
                (task for task in plan.tasks.values() if task.status == TaskStatus.FAILED),
                None,
            )
            if failed_task is None:
                return context

            raw_failure_class = (failed_task.error or {}).get("failure_class")
            try:
                failure_class = FailureClass(raw_failure_class)  # type: ignore
            except (ValueError, TypeError):
                failure_class = FailureClass.UNKNOWN

            recovery_preview = self.recovery.classify(failure_class, context)
            supervision = self.supervisor.decide(
                SupervisionRequest(
                    objective=objective,
                    plan_validated=True,
                    authorized=True,
                    status="failed",
                    failure=failure_class,
                    retry_allowed=recovery_preview.retry_allowed,
                    recovery_allowed=not recovery_preview.terminal,
                )
            )
            self.runtime.evidence.record(
                context.identity.execution_id,
                "execution.supervisor_decision",
                {
                    "task_id": failed_task.task_id,
                    "capability_id": failed_task.capability_id,
                    "action": supervision.action,
                    "reason": supervision.reason,
                },
            )

            if supervision.action == SupervisionAction.STOP:
                context.set_status(ExecutionStatus.STOPPED)
                self.runtime.checkpoint_store.save(context)
                return context

            if supervision.action != SupervisionAction.RETRY:
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
                return context

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

            failed_task.status = TaskStatus.PENDING
            failed_task.error = None
            failed_task.output = None

"""Integrated P0 control-plane to Kernel execution seam."""

from __future__ import annotations

from collections.abc import Mapping

from ois.kernel import (
    ExecutionContext,
    ExecutionIdentity,
    ExecutionPlan,
    ExecutionRuntime,
    PlanBuilder,
    PlanOrchestrator,
)

from .controller import ControlPlane
from .request import ControlRequest


class IntegratedExecution:
    """Submit a registered capability through the authoritative Kernel."""

    def __init__(
        self,
        control_plane: ControlPlane,
        runtime: ExecutionRuntime,
    ) -> None:
        self.control_plane = control_plane
        self.orchestrator = PlanOrchestrator(runtime)

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
        self.orchestrator.execute(plan, context)
        return context

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ois.capabilities.tiktok_growth import TikTokContentAgent
from ois.kernel.checkpoint import InMemoryCheckpointStore
from ois.kernel.contracts import InvocationResult
from ois.kernel.evidence import EvidenceEvent, EvidenceLedger
from ois.kernel.orchestrator import PlanOrchestrator
from ois.kernel.planning import ExecutionPlan, TaskNode
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity


VERTICAL_SLICE_WORKFLOW_ID = "tiktok.content.vertical_slice"
VERTICAL_SLICE_VERSION = "1.0.0"


@dataclass(frozen=True)
class VerticalSliceResult:
    """Complete result of the canonical OIS vertical execution slice."""

    context: ExecutionContext
    plan: ExecutionPlan
    invocation: InvocationResult
    evidence: tuple[EvidenceEvent, ...]


def build_tiktok_vertical_plan(input_data: dict[str, Any]) -> ExecutionPlan:
    """Build the smallest real OIS workflow that exercises the kernel end-to-end."""
    plan = ExecutionPlan(
        version=VERTICAL_SLICE_VERSION,
        objective="Create a governed TikTok content plan",
        metadata={"workflow_id": VERTICAL_SLICE_WORKFLOW_ID},
    )
    plan.add_task(
        TaskNode(
            task_id="create_content_plan",
            capability_id="tiktok.content.plan",
            capability_version="1.0.0",
            input_data=input_data,
            metadata={"role": "domain_capability"},
        )
    )
    plan.validate()
    return plan


def execute_tiktok_vertical_slice(
    input_data: dict[str, Any],
    *,
    tenant_id: str = "default",
) -> VerticalSliceResult:
    """Execute the canonical OIS vertical slice through the existing kernel."""
    registry = CapabilityRegistry()
    registry.register(TikTokContentAgent())

    checkpoint_store = InMemoryCheckpointStore()
    evidence = EvidenceLedger()
    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=checkpoint_store,
        evidence=evidence,
    )
    orchestrator = PlanOrchestrator(runtime)

    identity = ExecutionIdentity(
        tenant_id=tenant_id,
        workflow_id=VERTICAL_SLICE_WORKFLOW_ID,
        workflow_version=VERTICAL_SLICE_VERSION,
    )
    context = ExecutionContext(
        identity=identity,
        objective="Create a governed TikTok content plan",
        metadata={"vertical_slice": True},
    )
    context.intent = {"type": "content_plan", "input": dict(input_data)}

    plan = build_tiktok_vertical_plan(input_data)
    context.plan = {
        "plan_id": plan.plan_id,
        "version": plan.version,
        "workflow_id": VERTICAL_SLICE_WORKFLOW_ID,
        "task_ids": tuple(plan.tasks),
    }

    executed_plan = orchestrator.execute(plan, context)
    task = executed_plan.tasks["create_content_plan"]
    invocation = runtime.idempotency.get(
        f"{context.identity.execution_id}:create_content_plan"
    )
    if invocation is None:
        raise RuntimeError("Vertical slice completed without an invocation result.")

    if not checkpoint_store.exists(context.identity.execution_id):
        raise RuntimeError("Vertical slice completed without a checkpoint.")

    return VerticalSliceResult(
        context=checkpoint_store.load(context.identity.execution_id),
        plan=executed_plan,
        invocation=invocation,
        evidence=evidence.list(context.identity.execution_id),
    )

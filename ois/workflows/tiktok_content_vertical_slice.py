from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ois.capabilities.tiktok_growth import TikTokContentAgent
from ois.kernel.checkpoint import InMemoryCheckpointStore
from ois.kernel.contracts import InvocationResult
from ois.kernel.evidence import EvidenceEvent, EvidenceLedger
from ois.kernel.orchestrator import PlanOrchestrator
from ois.kernel.planning import ExecutionPlan, TaskNode
from ois.kernel.registry import AgentRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.supervisor import Supervisor

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
    """Execute the canonical OIS vertical slice through Supervisor and kernel."""
    agent = TikTokContentAgent()
    agent_registry = AgentRegistry()
    agent_registry.register(agent)

    checkpoint_store = InMemoryCheckpointStore()
    evidence = EvidenceLedger()
    runtime = ExecutionRuntime(
        registry=agent_registry,
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
        metadata={"vertical_slice": True, "supervised": True},
    )
    context.intent = {"type": "content_plan", "input": dict(input_data)}

    plan = build_tiktok_vertical_plan(input_data)
    context.plan = {
        "plan_id": plan.plan_id,
        "version": plan.version,
        "workflow_id": VERTICAL_SLICE_WORKFLOW_ID,
        "task_ids": tuple(plan.tasks),
    }

    # Supervisor is the governed delegation boundary. It selects the exact
    # registered agent before handing the unchanged plan to the existing
    # orchestrator/runtime path. No second execution path is introduced.
    supervisor = Supervisor(
        runtime=runtime,
        agent_registry=agent_registry,
        orchestrator=orchestrator,
        evidence=evidence,
    )
    selected = supervisor.select_agent(
        "tiktok.content.plan",
        "1.0.0",
        context=context,
        input_data=input_data,
        invocation_id=f"{context.identity.execution_id}:agent-selection",
    )
    context.metadata["supervisor_selection"] = {
        "capability_id": selected.contract.capability_id,
        "version": selected.contract.version,
        "agent_type": (
            f"{type(selected.capability).__module__}."
            f"{type(selected.capability).__qualname__}"
        ),
    }

    executed_plan = supervisor.execute(plan, context)
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

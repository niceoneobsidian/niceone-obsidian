"""Phase C application boundary for autonomous source operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ois.infrastructure.source_gateway.outbox import OutboxEvent, OutboxStore

from .approvals import ApprovalDecision, ApprovalGate, InMemoryApprovalStore
from .events import EventEnvelope, EventRoute, InMemoryEventRouter
from .loops import AutonomousLoop, LoopDecision
from .policy import AutomationPolicy
from .recovery import FailureRecovery
from .workflows import SourceWorkflow, WorkflowRun


@dataclass(frozen=True)
class OperationReceipt:
    event_id: str
    workflow_ids: tuple[str, ...]
    decisions: tuple[LoopDecision, ...]


class AutonomousOperations:
    """Build 15–20 on one governed event -> workflow -> policy -> execution path."""

    def __init__(
        self,
        *,
        outbox: OutboxStore | None = None,
        policy: AutomationPolicy | None = None,
        approvals: InMemoryApprovalStore | None = None,
        recovery: FailureRecovery | None = None,
        max_iterations: int = 3,
    ) -> None:
        self._outbox = outbox
        self._approvals = approvals or InMemoryApprovalStore()
        self._loop = AutonomousLoop(
            policy=policy or AutomationPolicy(),
            approval_gate=ApprovalGate(self._approvals),
            recovery=recovery or FailureRecovery(),
            max_iterations=max_iterations,
        )
        self._router = InMemoryEventRouter()
        self._workflows: dict[str, SourceWorkflow] = {}
        self._processed: set[tuple[str, str]] = set()

    @property
    def router(self) -> InMemoryEventRouter:
        return self._router

    @property
    def approvals(self) -> InMemoryApprovalStore:
        return self._approvals

    def register_workflow(self, workflow: SourceWorkflow) -> None:
        if workflow.workflow_id in self._workflows:
            raise ValueError(f"workflow already registered: {workflow.workflow_id}")
        self._workflows[workflow.workflow_id] = workflow

        self._router.register(
            EventRoute(
                route_id=workflow.workflow_id,
                event_type=workflow.trigger.event_type,
                source_id=workflow.trigger.source_id,
                handler=lambda event, workflow_id=workflow.workflow_id: self._run_workflow(
                    workflow_id, event
                ),
            )
        )

    def route(self, event: EventEnvelope) -> OperationReceipt:
        results = self._router.route(event)
        decisions = tuple(item for item in results if isinstance(item, LoopDecision))
        workflow_ids = tuple(
            workflow_id
            for workflow_id, workflow in self._workflows.items()
            if workflow.matches(event)
        )
        return OperationReceipt(event.event_id, workflow_ids, decisions)

    def drain_outbox(self, *, limit: int = 100) -> tuple[OperationReceipt, ...]:
        if self._outbox is None:
            raise RuntimeError("outbox is not configured")
        receipts: list[OperationReceipt] = []
        for event in self._outbox.pending(limit=limit):
            receipt = self.route(EventEnvelope.from_outbox(event))
            receipts.append(receipt)
            if receipt.decisions and all(
                decision.state.value == "idle" for decision in receipt.decisions
            ):
                self._outbox.mark_published(event.event_id)
        return tuple(receipts)

    def approve_and_resume(self, approval_id: str, actor: str) -> LoopDecision:
        approval = self._approvals.decide(approval_id, ApprovalDecision.APPROVED, actor)
        workflow = self._workflows.get(approval.workflow_id)
        if workflow is None:
            raise KeyError(f"workflow not registered: {approval.workflow_id}")
        event = EventEnvelope(
            event_id=approval.event_id,
            tenant_id=approval.tenant_id,
            workspace_id=approval.workspace_id,
            event_type=workflow.trigger.event_type,
            aggregate_id=approval.event_id,
        )
        return self._run_workflow(workflow.workflow_id, event)

    def reject(self, approval_id: str, actor: str) -> None:
        self._approvals.decide(approval_id, ApprovalDecision.REJECTED, actor)

    def _run_workflow(self, workflow_id: str, event: EventEnvelope) -> LoopDecision:
        key = (workflow_id, event.event_id)
        if key in self._processed:
            return LoopDecision(
                state="idle",
                reason="workflow event already processed",
            )
        workflow = self._workflows[workflow_id]
        decision = self._loop.run(workflow=workflow, event=event)
        if decision.state.value == "idle":
            self._processed.add(key)
        return decision

"""Bounded autonomous operating loops."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from .approvals import ApprovalGate
from .events import EventEnvelope
from .policy import AutomationPolicy, PolicyOutcome
from .recovery import FailureRecovery
from .workflows import SourceWorkflow, WorkflowRun


class LoopState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    RECOVERING = "recovering"
    STOPPED = "stopped"


@dataclass(frozen=True)
class LoopDecision:
    state: LoopState
    workflow_run: WorkflowRun | None = None
    approval_id: str | None = None
    reason: str = ""


class AutonomousLoop:
    """Bounded event->policy->approval->execution->recovery control loop."""

    def __init__(
        self,
        *,
        policy: AutomationPolicy,
        approval_gate: ApprovalGate,
        recovery: FailureRecovery,
        max_iterations: int = 3,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        self._policy = policy
        self._approval_gate = approval_gate
        self._recovery = recovery
        self._max_iterations = max_iterations

    def run(
        self,
        *,
        workflow: SourceWorkflow,
        event: EventEnvelope,
        execute: Callable[[SourceWorkflow, EventEnvelope], object] | None = None,
        approval_granted: bool = False,
    ) -> LoopDecision:
        if not workflow.matches(event):
            return LoopDecision(LoopState.STOPPED, reason="workflow trigger did not match")

        context = dict(event.payload)
        context["event_type"] = event.event_type
        evaluation = self._policy.evaluate(context)

        if evaluation.outcome == PolicyOutcome.DENY:
            return LoopDecision(LoopState.STOPPED, reason=evaluation.reason)

        if evaluation.outcome == PolicyOutcome.APPROVAL_REQUIRED and not approval_granted:
            approval = self._approval_gate.request(
                tenant_id=event.tenant_id,
                workspace_id=event.workspace_id,
                workflow_id=workflow.workflow_id,
                event_id=event.event_id,
                event=event,
                reason=evaluation.reason,
            )
            return LoopDecision(LoopState.WAITING_APPROVAL, approval_id=approval.approval_id)

        def default_runner(wf: SourceWorkflow, evt: EventEnvelope) -> object:
            return wf.action(evt)

        runner: Callable[[SourceWorkflow, EventEnvelope], object] = execute or default_runner
        for attempt in range(1, self._max_iterations + 1):
            try:
                result = runner(workflow, event)
                return LoopDecision(
                    LoopState.IDLE,
                    workflow_run=WorkflowRun.success(workflow, event, result),
                    reason="workflow completed",
                )
            except Exception as exc:
                decision = self._recovery.decide(
                    attempt=attempt,
                    failure="transient",
                    safe_to_retry=True,
                )
                if decision.action.value == "retry":
                    continue
                return LoopDecision(
                    LoopState.RECOVERING,
                    workflow_run=WorkflowRun.failure(workflow, event, exc),
                    reason=decision.reason,
                )
        return LoopDecision(LoopState.RECOVERING, reason="recovery attempt limit exhausted")

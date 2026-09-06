"""Governed supervisor for OIS execution decisions.

The supervisor coordinates execution; it never grants authority. Policy and the
Kernel remain the authoritative authorization/execution boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ois.kernel.types import FailureClass


class SupervisionAction(StrEnum):
    EXECUTE = "execute"
    COMPLETE = "complete"
    RETRY = "retry"
    REPLAN = "replan"
    ESCALATE = "escalate"
    STOP = "stop"


@dataclass(frozen=True)
class SupervisionRequest:
    objective: str
    plan_validated: bool
    authorized: bool
    status: str
    failure: FailureClass | None = None
    retry_allowed: bool = False
    recovery_allowed: bool = False
    approval_required: bool = False
    approval_granted: bool = False


@dataclass(frozen=True)
class SupervisionDecision:
    action: SupervisionAction
    reason: str


class Supervisor:
    """Deterministic execution-governance coordinator.

    This component decides what should happen next from already-authorized
    state. It does not perform authorization, invoke tools, or mutate policy.
    """

    def decide(self, request: SupervisionRequest) -> SupervisionDecision:
        if not request.objective.strip():
            return SupervisionDecision(SupervisionAction.STOP, "objective is required")

        if request.approval_required and not request.approval_granted:
            return SupervisionDecision(
                SupervisionAction.ESCALATE,
                "human approval is required before execution",
            )

        if not request.authorized:
            return SupervisionDecision(
                SupervisionAction.ESCALATE,
                "authorization is not granted by the execution boundary",
            )

        if not request.plan_validated:
            return SupervisionDecision(
                SupervisionAction.REPLAN,
                "execution plan has not passed validation",
            )

        if request.status in {"completed", "success", "succeeded"}:
            return SupervisionDecision(
                SupervisionAction.COMPLETE,
                "execution completed successfully",
            )

        if request.failure == FailureClass.SAFETY:
            return SupervisionDecision(
                SupervisionAction.STOP,
                "safety failures terminate execution",
            )

        if request.failure == FailureClass.PERMISSION:
            return SupervisionDecision(
                SupervisionAction.ESCALATE,
                "permission failures require escalation",
            )

        if request.failure == FailureClass.PLAN:
            return SupervisionDecision(
                SupervisionAction.REPLAN,
                "plan failure requires a new executable plan",
            )

        if request.retry_allowed:
            return SupervisionDecision(
                SupervisionAction.RETRY,
                "bounded retry is permitted by recovery policy",
            )

        if request.recovery_allowed:
            return SupervisionDecision(
                SupervisionAction.REPLAN,
                "bounded recovery is permitted; replan before continuing",
            )

        if request.failure is not None:
            return SupervisionDecision(
                SupervisionAction.ESCALATE,
                f"failure {request.failure.value} has no safe automatic action",
            )

        return SupervisionDecision(SupervisionAction.EXECUTE, "plan is authorized and ready")

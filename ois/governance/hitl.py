"""Human-in-the-loop approval state machine for governed OIS side effects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from datetime import UTC, datetime


class ApprovalState(StrEnum):
    NOT_REQUIRED = "not_required"
    APPROVAL_REQUIRED = "approval_required"
    WAITING_FOR_HUMAN = "waiting_for_human"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    execution_id: str
    tenant_id: str
    action: str
    plan_version: str
    side_effect_summary: str
    requested_at: str
    expires_at: str
    state: ApprovalState = ApprovalState.WAITING_FOR_HUMAN


@dataclass(frozen=True)
class ApprovalDecision:
    approval_id: str
    state: ApprovalState
    decided_by: str | None
    decided_at: str
    reason: str | None = None


class HITLGate:
    """Fail-closed approval boundary; approval never grants permissions."""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._decisions: dict[str, ApprovalDecision] = {}

    def request(self, approval: ApprovalRequest) -> ApprovalRequest:
        if approval.approval_id in self._requests:
            raise ValueError(f"approval already exists: {approval.approval_id}")
        if not approval.execution_id or not approval.tenant_id or not approval.action:
            raise ValueError("approval requires execution, tenant, and action")
        self._requests[approval.approval_id] = approval
        return approval

    def decide(self, approval_id: str, *, approved: bool, actor: str, reason: str | None = None) -> ApprovalDecision:
        request = self._requests[approval_id]
        if request.state is not ApprovalState.WAITING_FOR_HUMAN:
            raise ValueError(f"approval is not pending: {approval_id}")
        if not actor:
            raise ValueError("approval decision requires an authenticated actor")
        decision = ApprovalDecision(
            approval_id=approval_id,
            state=ApprovalState.APPROVED if approved else ApprovalState.REJECTED,
            decided_by=actor,
            decided_at=datetime.now(UTC).isoformat(),
            reason=reason,
        )
        self._decisions[approval_id] = decision
        return decision

    def authorize(self, approval_id: str) -> bool:
        """Return approval status only; callers must still pass normal policy checks."""
        decision = self._decisions.get(approval_id)
        return decision is not None and decision.state is ApprovalState.APPROVED

    def decision(self, approval_id: str) -> ApprovalDecision | None:
        return self._decisions.get(approval_id)

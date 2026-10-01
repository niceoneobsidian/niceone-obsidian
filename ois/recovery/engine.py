"""Explicit recovery decisions and state-machine integration."""

from __future__ import annotations

from dataclasses import dataclass

from ois.application.state import ExecutionState, transition


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    reason: str
    next_state: ExecutionState | None = None


class RecoveryPlane:
    def decide(self, *, failure: str, attempt: int, max_attempts: int) -> RecoveryDecision:
        if attempt < max_attempts:
            return RecoveryDecision("retry", failure, ExecutionState.RETRY_PENDING)
        return RecoveryDecision("escalate", failure, ExecutionState.ESCALATION_REQUIRED)

    def apply(self, current: ExecutionState, decision: RecoveryDecision) -> ExecutionState:
        if decision.next_state is None:
            return current
        return transition(current, decision.next_state)


# Backward-compatible name used by existing callers.
RecoveryPlan = RecoveryPlane

"""Explicit execution and recovery state machines."""

from enum import StrEnum


class ExecutionState(StrEnum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    VALIDATING = "validating"
    VERIFIED = "verified"
    RETRY_PENDING = "retry_pending"
    ROLLBACK_PENDING = "rollback_pending"
    ESCALATION_REQUIRED = "escalation_required"
    FAILED = "failed"


_ALLOWED: dict[ExecutionState, frozenset[ExecutionState]] = {
    ExecutionState.PENDING: frozenset({ExecutionState.AUTHORIZED, ExecutionState.FAILED}),
    ExecutionState.AUTHORIZED: frozenset({ExecutionState.EXECUTING, ExecutionState.FAILED}),
    ExecutionState.EXECUTING: frozenset({ExecutionState.VALIDATING, ExecutionState.RETRY_PENDING, ExecutionState.ROLLBACK_PENDING, ExecutionState.FAILED}),
    ExecutionState.VALIDATING: frozenset({ExecutionState.VERIFIED, ExecutionState.RETRY_PENDING, ExecutionState.ROLLBACK_PENDING, ExecutionState.FAILED}),
    ExecutionState.VERIFIED: frozenset(),
    ExecutionState.RETRY_PENDING: frozenset({ExecutionState.AUTHORIZED, ExecutionState.ESCALATION_REQUIRED, ExecutionState.FAILED}),
    ExecutionState.ROLLBACK_PENDING: frozenset({ExecutionState.FAILED, ExecutionState.ESCALATION_REQUIRED}),
    ExecutionState.ESCALATION_REQUIRED: frozenset({ExecutionState.FAILED}),
    ExecutionState.FAILED: frozenset(),
}


def transition(current: ExecutionState, target: ExecutionState) -> ExecutionState:
    """Return target only for a declared transition; otherwise fail closed."""
    if target not in _ALLOWED[current]:
        raise ValueError(f"invalid execution transition: {current} -> {target}")
    return target

"""Fail-closed execution state machine shared by execution and recovery."""

from __future__ import annotations

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


_TRANSITIONS: dict[ExecutionState, frozenset[ExecutionState]] = {
    ExecutionState.PENDING: frozenset({ExecutionState.AUTHORIZED, ExecutionState.FAILED}),
    ExecutionState.AUTHORIZED: frozenset({ExecutionState.EXECUTING, ExecutionState.FAILED}),
    ExecutionState.EXECUTING: frozenset(
        {
            ExecutionState.VALIDATING,
            ExecutionState.ROLLBACK_PENDING,
            ExecutionState.FAILED,
        }
    ),
    ExecutionState.VALIDATING: frozenset(
        {
            ExecutionState.VERIFIED,
            ExecutionState.RETRY_PENDING,
            ExecutionState.ROLLBACK_PENDING,
            ExecutionState.ESCALATION_REQUIRED,
            ExecutionState.FAILED,
        }
    ),
    ExecutionState.VERIFIED: frozenset(),
    ExecutionState.RETRY_PENDING: frozenset(
        {ExecutionState.EXECUTING, ExecutionState.ESCALATION_REQUIRED}
    ),
    ExecutionState.ROLLBACK_PENDING: frozenset({ExecutionState.FAILED, ExecutionState.VERIFIED}),
    ExecutionState.ESCALATION_REQUIRED: frozenset(),
    ExecutionState.FAILED: frozenset(),
}


def transition(current: ExecutionState, target: ExecutionState) -> ExecutionState:
    if target not in _TRANSITIONS[current]:
        raise ValueError(f"invalid execution transition: {current} -> {target}")
    return target

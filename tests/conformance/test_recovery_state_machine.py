import pytest

from ois.application.state import ExecutionState, transition
from ois.recovery.engine import RecoveryPlane


def test_retry_decision_enters_retry_pending():
    decision = RecoveryPlane().decide(failure="timeout", attempt=1, max_attempts=3)
    assert decision.action == "retry"
    assert (
        RecoveryPlane().apply(ExecutionState.VALIDATING, decision) == ExecutionState.RETRY_PENDING
    )


def test_exhausted_recovery_escalates():
    decision = RecoveryPlane().decide(failure="timeout", attempt=3, max_attempts=3)
    assert decision.action == "escalate"
    assert (
        RecoveryPlane().apply(ExecutionState.VALIDATING, decision)
        == ExecutionState.ESCALATION_REQUIRED
    )


def test_invalid_transition_fails_closed():
    with pytest.raises(ValueError):
        transition(ExecutionState.VERIFIED, ExecutionState.EXECUTING)

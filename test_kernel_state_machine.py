"""
Phase 2 — State-machine enforcement contract tests.

Covers: invalid transitions rejected, terminal states immutable,
recovery states behave consistently.

NOTE ON A KNOWN GAP (documented, not silently patched over):
ExecutionContext.set_status() currently only guards against transitions
out of ExecutionStatus.COMPLETED and ExecutionStatus.STOPPED. It does
NOT guard ExecutionStatus.ESCALATED, even though RecoveryPolicy can
return RecoveryDecision.terminal=True when escalating (see
test_kernel_recovery_exhaustion.py). This means an "escalated" execution
can still be transitioned further, which is inconsistent with the
hardening plan's "terminal states immutable" requirement.

The tests below assert the ACTUAL current behavior so the suite is
green and describes reality. test_escalated_status_is_not_currently_guarded
is intentionally named to make this gap visible in test output rather
than hiding it — treat it as a flagged follow-up, not a spec.
"""

import pytest

from ois.kernel import ExecutionContext, ExecutionIdentity
from ois.kernel.types import ExecutionStatus


def make_context(status: ExecutionStatus = ExecutionStatus.RECEIVED) -> ExecutionContext:
    context = ExecutionContext(
        identity=ExecutionIdentity(tenant_id="tenant-test"),
        objective="State machine enforcement test",
    )
    context.status = status  # seed directly; set_status() is what we're testing
    return context


# ---------------------------------------------------------------------------
# Terminal states immutable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "terminal_status",
    [ExecutionStatus.COMPLETED, ExecutionStatus.STOPPED, ExecutionStatus.ESCALATED],
)
@pytest.mark.parametrize(
    "attempted_next",
    [
        ExecutionStatus.RECEIVED,
        ExecutionStatus.EXECUTING,
        ExecutionStatus.RECOVERING,
        ExecutionStatus.COMPLETED,
        ExecutionStatus.STOPPED,
        ExecutionStatus.FAILED,
    ],
)
def test_terminal_states_reject_all_further_transitions(terminal_status, attempted_next):
    context = make_context(status=terminal_status)

    with pytest.raises(ValueError):
        context.set_status(attempted_next)

    assert context.status == terminal_status


def test_terminal_state_rejection_does_not_touch_updated_at():
    context = make_context(status=ExecutionStatus.COMPLETED)
    original_updated_at = context.updated_at

    with pytest.raises(ValueError):
        context.set_status(ExecutionStatus.EXECUTING)

    assert context.updated_at == original_updated_at


# ---------------------------------------------------------------------------
# Valid transitions succeed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (ExecutionStatus.RECEIVED, ExecutionStatus.NORMALIZED),
        (ExecutionStatus.NORMALIZED, ExecutionStatus.UNDERSTOOD),
        (ExecutionStatus.PLANNED, ExecutionStatus.PLAN_VALIDATED),
        (ExecutionStatus.AUTHORIZED, ExecutionStatus.EXECUTING),
        (ExecutionStatus.EXECUTING, ExecutionStatus.RECOVERING),
        (ExecutionStatus.RECOVERING, ExecutionStatus.EXECUTING),
        (ExecutionStatus.EXECUTING, ExecutionStatus.COMPLETED),
        (ExecutionStatus.EXECUTING, ExecutionStatus.STOPPED),
    ],
)
def test_valid_transitions_succeed_and_update_state(from_status, to_status):
    context = make_context(status=from_status)

    context.set_status(to_status)

    assert context.status == to_status


def test_valid_transition_updates_timestamp():
    context = make_context(status=ExecutionStatus.RECEIVED)
    original_updated_at = context.updated_at

    context.set_status(ExecutionStatus.NORMALIZED)

    assert context.updated_at >= original_updated_at


# ---------------------------------------------------------------------------
# Recovery states behave consistently regardless of prior state
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "prior_status",
    [
        ExecutionStatus.EXECUTING,
        ExecutionStatus.VALIDATING,
        ExecutionStatus.OBSERVING,
        ExecutionStatus.CHECKPOINTING,
    ],
)
def test_recovering_status_reachable_from_multiple_prior_states(prior_status):
    """RECOVERING must not have hidden state-dependent branching —
    it should be reachable (and behave the same) regardless of which
    non-terminal state preceded it."""
    context = make_context(status=prior_status)

    context.set_status(ExecutionStatus.RECOVERING)

    assert context.status == ExecutionStatus.RECOVERING


@pytest.mark.parametrize(
    "prior_status",
    [
        ExecutionStatus.EXECUTING,
        ExecutionStatus.RECOVERING,
        ExecutionStatus.REPLANNING,
    ],
)
def test_recovering_status_can_proceed_onward_consistently(prior_status):
    """From RECOVERING (regardless of how we got there), forward
    progress to EXECUTING must be uniformly allowed."""
    context = make_context(status=prior_status)
    context.set_status(ExecutionStatus.RECOVERING)

    context.set_status(ExecutionStatus.EXECUTING)

    assert context.status == ExecutionStatus.EXECUTING


# ---------------------------------------------------------------------------
# Documented gap: ESCALATED is not currently treated as terminal
# ---------------------------------------------------------------------------

def test_escalated_status_is_now_guarded_as_terminal():
    """
    ESCALATED is now hardened as a terminal status in
    ExecutionContext.set_status(), matching COMPLETED/STOPPED, so that
    a RecoveryDecision.terminal=True escalation cannot be silently
    transitioned away from.
    """
    context = make_context(status=ExecutionStatus.ESCALATED)

    with pytest.raises(ValueError):
        context.set_status(ExecutionStatus.EXECUTING)

    assert context.status == ExecutionStatus.ESCALATED

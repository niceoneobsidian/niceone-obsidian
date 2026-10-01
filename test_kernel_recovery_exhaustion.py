"""
Phase 1 — Recovery exhaustion contract tests.

Covers: retry limit, recovery-attempt limit, terminal escalation/stop
behavior, as defined in ois.kernel.recovery.RecoveryPolicy.

These tests exercise RecoveryPolicy directly (unit-level, deterministic,
no runtime/supervisor/orchestrator involved) so failures point precisely
at the recovery policy rather than at integration plumbing.
"""

import pytest

from ois.kernel import ExecutionContext, ExecutionIdentity
from ois.kernel.recovery import RecoveryPolicy
from ois.kernel.types import ExecutionStatus, FailureClass


def make_context() -> ExecutionContext:
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="tenant-test"),
        objective="Recovery exhaustion test",
    )


# ---------------------------------------------------------------------------
# Retry limit (transient failures)
# ---------------------------------------------------------------------------


def test_transient_retries_until_limit_then_escalates():  # type: ignore
    policy = RecoveryPolicy(max_retries=2, max_recovery_attempts=3)
    context = make_context()

    first = policy.apply(context, FailureClass.TRANSIENT)
    assert first.action == "retry"
    assert first.retry_allowed is True
    assert first.terminal is False
    assert context.retry_count == 1
    assert context.status == ExecutionStatus.RECOVERING

    second = policy.apply(context, FailureClass.TRANSIENT)
    assert second.action == "retry"
    assert context.retry_count == 2
    assert context.status == ExecutionStatus.RECOVERING

    third = policy.apply(context, FailureClass.TRANSIENT)
    assert third.action == "escalate"
    assert third.retry_allowed is False
    assert third.terminal is True
    assert context.status == ExecutionStatus.ESCALATED  # type: ignore

    # retry_count must not keep incrementing once retries are exhausted
    assert context.retry_count == 2


def test_transient_retry_boundary_zero_retries_escalates_immediately():  # type: ignore
    policy = RecoveryPolicy(max_retries=0, max_recovery_attempts=3)
    context = make_context()

    decision = policy.apply(context, FailureClass.TRANSIENT)

    assert decision.action == "escalate"
    assert decision.terminal is True
    assert context.retry_count == 0
    assert context.status == ExecutionStatus.ESCALATED


def test_transient_retry_boundary_one_retry_allows_exactly_one():  # type: ignore
    policy = RecoveryPolicy(max_retries=1, max_recovery_attempts=3)
    context = make_context()

    first = policy.apply(context, FailureClass.TRANSIENT)
    assert first.action == "retry"
    assert context.retry_count == 1

    second = policy.apply(context, FailureClass.TRANSIENT)
    assert second.action == "escalate"
    assert second.terminal is True


# ---------------------------------------------------------------------------
# Recovery-attempt limit (state failures) — distinct counter from retries
# ---------------------------------------------------------------------------


def test_state_recovery_attempts_until_limit_then_escalates():  # type: ignore
    policy = RecoveryPolicy(max_retries=2, max_recovery_attempts=2)
    context = make_context()

    first = policy.apply(context, FailureClass.STATE)
    assert first.action == "recover"
    assert first.terminal is False
    assert context.recovery_attempts == 1
    assert context.status == ExecutionStatus.RECOVERING

    second = policy.apply(context, FailureClass.STATE)
    assert second.action == "recover"
    assert context.recovery_attempts == 2

    third = policy.apply(context, FailureClass.STATE)
    assert third.action == "escalate"
    assert third.terminal is True
    assert context.status == ExecutionStatus.ESCALATED  # type: ignore
    assert context.recovery_attempts == 2  # unchanged once exhausted


def test_retry_count_and_recovery_attempts_are_independent_counters():  # type: ignore
    """A task can exhaust retries without touching recovery_attempts,
    and vice versa — the two limits must not bleed into each other."""
    policy = RecoveryPolicy(max_retries=1, max_recovery_attempts=1)
    context = make_context()

    policy.apply(context, FailureClass.TRANSIENT)  # retry_count -> 1
    assert context.retry_count == 1
    assert context.recovery_attempts == 0

    policy.apply(context, FailureClass.STATE)  # recovery_attempts -> 1
    assert context.recovery_attempts == 1
    assert context.retry_count == 1  # untouched by STATE failure


# ---------------------------------------------------------------------------
# Terminal escalation / stop behavior
# ---------------------------------------------------------------------------


def test_safety_failure_always_stops_regardless_of_counters():  # type: ignore
    policy = RecoveryPolicy(max_retries=5, max_recovery_attempts=5)
    context = make_context()

    decision = policy.apply(context, FailureClass.SAFETY)

    assert decision.action == "stop"
    assert decision.terminal is True
    assert context.status == ExecutionStatus.STOPPED


def test_stop_is_reached_even_on_first_safety_failure():  # type: ignore
    """Safety failures must terminate immediately — no retry budget
    should apply, unlike transient/state failures."""
    policy = RecoveryPolicy(max_retries=0, max_recovery_attempts=0)
    context = make_context()

    decision = policy.apply(context, FailureClass.SAFETY)

    assert decision.terminal is True
    assert context.status == ExecutionStatus.STOPPED
    assert context.retry_count == 0
    assert context.recovery_attempts == 0


def test_permission_failure_escalates_but_is_not_marked_terminal():  # type: ignore
    """Permission failures escalate but RecoveryDecision.terminal is False
    per current policy — documented here so a future change to this
    behavior is a deliberate decision, not an accidental regression."""
    policy = RecoveryPolicy()
    context = make_context()

    decision = policy.apply(context, FailureClass.PERMISSION)

    assert decision.action == "escalate"
    assert decision.terminal is False
    assert context.status == ExecutionStatus.ESCALATED


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


def test_negative_max_retries_rejected():  # type: ignore
    with pytest.raises(ValueError):
        RecoveryPolicy(max_retries=-1)


def test_negative_max_recovery_attempts_rejected():  # type: ignore
    with pytest.raises(ValueError):
        RecoveryPolicy(max_recovery_attempts=-1)


# ---------------------------------------------------------------------------
# Error/context bookkeeping
# ---------------------------------------------------------------------------


def test_apply_records_failure_and_error_detail_on_context():  # type: ignore
    policy = RecoveryPolicy()
    context = make_context()

    decision = policy.apply(context, FailureClass.TOOL)

    assert context.last_failure == FailureClass.TOOL
    assert context.error is not None
    assert context.error["failure_class"] == FailureClass.TOOL.value
    assert context.error["recovery_action"] == decision.action
    assert context.error["reason"] == decision.reason

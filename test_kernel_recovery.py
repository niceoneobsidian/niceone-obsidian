import pytest

from ois.kernel import ExecutionContext, ExecutionIdentity
from ois.kernel.recovery import RecoveryPolicy
from ois.kernel.types import ExecutionStatus, FailureClass


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="default"),
        objective="Recovery test",
    )


def test_transient_failure_retries():
    policy = RecoveryPolicy(max_retries=2)
    context = make_context()

    decision = policy.apply(context, FailureClass.TRANSIENT)

    assert decision.action == "retry"
    assert decision.retry_allowed is True
    assert decision.terminal is False
    assert context.retry_count == 1
    assert context.status == ExecutionStatus.RECOVERING


def test_transient_retry_limit_escalates():
    policy = RecoveryPolicy(max_retries=2)
    context = make_context()
    context.retry_count = 2

    decision = policy.apply(context, FailureClass.TRANSIENT)

    assert decision.action == "escalate"
    assert decision.terminal is True
    assert context.status == ExecutionStatus.ESCALATED


def test_parameter_failure_requires_correction():
    policy = RecoveryPolicy()
    context = make_context()

    decision = policy.apply(context, FailureClass.PARAMETER)

    assert decision.action == "correct"
    assert decision.retry_allowed is False
    assert decision.terminal is False
    assert context.status == ExecutionStatus.RECEIVED


def test_tool_failure_uses_fallback():
    policy = RecoveryPolicy()
    context = make_context()

    decision = policy.apply(context, FailureClass.TOOL)

    assert decision.action == "fallback"
    assert decision.retry_allowed is False
    assert decision.terminal is False
    assert context.status == ExecutionStatus.RECEIVED


def test_plan_failure_triggers_replan():
    policy = RecoveryPolicy()
    context = make_context()

    decision = policy.apply(context, FailureClass.PLAN)

    assert decision.action == "replan"
    assert decision.retry_allowed is False
    assert decision.terminal is False
    assert context.recovery_attempts == 1
    assert context.status == ExecutionStatus.REPLANNING


def test_state_failure_recovers():
    policy = RecoveryPolicy(max_recovery_attempts=2)
    context = make_context()

    decision = policy.apply(context, FailureClass.STATE)

    assert decision.action == "recover"
    assert decision.retry_allowed is False
    assert decision.terminal is False
    assert context.recovery_attempts == 1
    assert context.status == ExecutionStatus.RECOVERING


def test_state_recovery_limit_escalates():
    policy = RecoveryPolicy(max_recovery_attempts=2)
    context = make_context()
    context.recovery_attempts = 2

    decision = policy.apply(context, FailureClass.STATE)

    assert decision.action == "escalate"
    assert decision.terminal is True
    assert context.status == ExecutionStatus.ESCALATED


def test_permission_failure_escalates():
    policy = RecoveryPolicy()
    context = make_context()

    decision = policy.apply(context, FailureClass.PERMISSION)

    assert decision.action == "escalate"
    assert decision.retry_allowed is False
    assert decision.terminal is False
    assert context.status == ExecutionStatus.ESCALATED


def test_safety_failure_stops_execution():
    policy = RecoveryPolicy()
    context = make_context()

    decision = policy.apply(context, FailureClass.SAFETY)

    assert decision.action == "stop"
    assert decision.retry_allowed is False
    assert decision.terminal is True
    assert context.status == ExecutionStatus.STOPPED


def test_unknown_failure_escalates():
    policy = RecoveryPolicy()
    context = make_context()

    decision = policy.apply(context, FailureClass.UNKNOWN)

    assert decision.action == "escalate"
    assert decision.retry_allowed is False
    assert decision.terminal is False
    assert context.status == ExecutionStatus.ESCALATED


def test_recovery_records_failure_and_error():
    policy = RecoveryPolicy()
    context = make_context()

    decision = policy.apply(context, FailureClass.TRANSIENT)

    assert context.last_failure == FailureClass.TRANSIENT
    assert context.error is not None
    assert context.error["failure_class"] == "transient"
    assert context.error["recovery_action"] == decision.action
    assert "reason" in context.error


def test_invalid_recovery_limits_are_rejected():
    with pytest.raises(ValueError):
        RecoveryPolicy(max_retries=-1)

    with pytest.raises(ValueError):
        RecoveryPolicy(max_recovery_attempts=-1)

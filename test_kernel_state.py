import pytest

from ois.kernel import (
    ExecutionContext,
    ExecutionIdentity,
    ExecutionStatus,
)


def make_context():  # type: ignore
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="default"),
        objective="State transition test",
    )


def test_received_can_enter_normalized():  # type: ignore
    context = make_context()

    context.set_status(ExecutionStatus.NORMALIZED)

    assert context.status == ExecutionStatus.NORMALIZED


def test_active_lifecycle_can_reach_routed():  # type: ignore
    context = make_context()

    for status in (
        ExecutionStatus.NORMALIZED,
        ExecutionStatus.PLAN_VALIDATED,
        ExecutionStatus.AUTHORIZED,
        ExecutionStatus.EXECUTING,
        ExecutionStatus.OBSERVING,
        ExecutionStatus.VALIDATING,
        ExecutionStatus.UPDATING_STATE,
        ExecutionStatus.CHECKPOINTING,
        ExecutionStatus.ROUTED,
    ):
        context.set_status(status)

    assert context.status == ExecutionStatus.ROUTED


def test_routed_can_complete():  # type: ignore
    context = make_context()

    context.set_status(ExecutionStatus.ROUTED)
    context.set_status(ExecutionStatus.COMPLETED)

    assert context.status == ExecutionStatus.COMPLETED


def test_completed_is_terminal():  # type: ignore
    context = make_context()

    context.set_status(ExecutionStatus.COMPLETED)

    with pytest.raises(ValueError):
        context.set_status(ExecutionStatus.EXECUTING)


def test_stopped_is_terminal():  # type: ignore
    context = make_context()

    context.set_status(ExecutionStatus.STOPPED)

    with pytest.raises(ValueError):
        context.set_status(ExecutionStatus.EXECUTING)


def test_recovery_states_are_reachable():  # type: ignore
    for status in (
        ExecutionStatus.RECOVERING,
        ExecutionStatus.REPLANNING,
        ExecutionStatus.ESCALATED,
        ExecutionStatus.STOPPED,
    ):
        context = make_context()

        context.set_status(status)

        assert context.status == status

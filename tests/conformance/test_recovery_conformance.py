from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from ois.kernel.recovery import RecoveryPolicy
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import ExecutionStatus, FailureClass


@dataclass(frozen=True)
class RecoveryScenario:
    scenario_id: str
    failure: FailureClass
    expected_action: str
    expected_status: ExecutionStatus
    retry_count: int = 0
    recovery_attempts: int = 0


SCENARIOS = (
    RecoveryScenario("RC-01", FailureClass.TRANSIENT, "retry", ExecutionStatus.RECOVERING),
    RecoveryScenario("RC-02", FailureClass.TRANSIENT, "retry", ExecutionStatus.RECOVERING),
    RecoveryScenario("RC-03", FailureClass.TOOL, "fallback", ExecutionStatus.RECEIVED),
    RecoveryScenario("RC-04", FailureClass.PARAMETER, "correct", ExecutionStatus.RECEIVED),
    RecoveryScenario("RC-05", FailureClass.PERMISSION, "escalate", ExecutionStatus.ESCALATED),
    RecoveryScenario("RC-06", FailureClass.STATE, "recover", ExecutionStatus.RECOVERING),
    RecoveryScenario("RC-07", FailureClass.TRANSIENT, "escalate", ExecutionStatus.ESCALATED, 2),
    RecoveryScenario("RC-08", FailureClass.TOOL, "fallback", ExecutionStatus.RECEIVED),
    RecoveryScenario("RC-09", FailureClass.UNKNOWN, "escalate", ExecutionStatus.ESCALATED),
    RecoveryScenario("RC-10", FailureClass.STATE, "recover", ExecutionStatus.RECOVERING),
    RecoveryScenario("RC-11", FailureClass.SAFETY, "stop", ExecutionStatus.STOPPED),
    RecoveryScenario("RC-12", FailureClass.PERMISSION, "escalate", ExecutionStatus.ESCALATED),
)


@pytest.mark.recovery
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda item: item.scenario_id)
def test_recovery_matrix_is_deterministic(scenario: RecoveryScenario) -> None:
    context = ExecutionContext(
        identity=ExecutionIdentity(execution_id=uuid4(), tenant_id="conformance"),
        objective=f"recovery {scenario.scenario_id}",
        retry_count=scenario.retry_count,
        recovery_attempts=scenario.recovery_attempts,
    )
    decision = RecoveryPolicy(max_retries=2, max_recovery_attempts=3).apply(
        context, scenario.failure
    )

    assert decision.action == scenario.expected_action
    assert context.status == scenario.expected_status
    assert context.last_failure == scenario.failure
    assert context.error is not None
    assert context.error["failure_class"] == scenario.failure.value
    assert context.error["recovery_action"] == scenario.expected_action


@pytest.mark.recovery
def test_recovery_matrix_contains_exactly_twelve_unique_ids() -> None:
    ids = [scenario.scenario_id for scenario in SCENARIOS]
    assert len(ids) == 12
    assert len(set(ids)) == 12
    assert ids == [f"RC-{index:02d}" for index in range(1, 13)]


@pytest.mark.recovery
def test_terminal_states_reject_all_future_transitions() -> None:
    for terminal in (
        ExecutionStatus.COMPLETED,
        ExecutionStatus.STOPPED,
        ExecutionStatus.ESCALATED,
    ):
        context = ExecutionContext(
            identity=ExecutionIdentity(execution_id=uuid4()),
            objective="terminal transition conformance",
            status=terminal,
        )
        with pytest.raises(ValueError):
            context.set_status(ExecutionStatus.RECOVERING)

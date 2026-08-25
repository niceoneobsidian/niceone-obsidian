from ois.runtime.intelligence_fabrics import (
    DefaultIntelligenceFabric,
    ExecutionTarget,
)


def test_target_validation_rejects_missing_identity() -> None:
    fabric = DefaultIntelligenceFabric()
    result = fabric.validate_target(ExecutionTarget("", "run"))
    assert not result.is_valid


def test_target_validation_accepts_valid_target() -> None:
    fabric = DefaultIntelligenceFabric()
    result = fabric.validate_target(ExecutionTarget("target-1", "run"))
    assert result.is_valid


def test_recovery_is_bounded_and_escalates() -> None:
    fabric = DefaultIntelligenceFabric()
    target = ExecutionTarget("target-1", "run")

    assert fabric.handle_failure(target, RuntimeError("boom"), 0).action == "retry"
    assert fabric.handle_failure(target, RuntimeError("boom"), 3).action == "escalate"


def test_telemetry_event_is_structured() -> None:
    event = DefaultIntelligenceFabric().create_telemetry_event(
        "execution.completed", {"target_id": "target-1"}
    )
    assert event.event_type == "execution.completed"
    assert event.plane == "IntelligenceFabric"

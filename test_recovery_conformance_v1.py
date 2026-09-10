import json

import pytest

from ois.kernel.cancellation import CancellationToken, ExecutionCancellation
from ois.kernel.checkpoint import CheckpointError, JsonFileCheckpointStore
from ois.kernel.contracts import InvocationResult
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.idempotency import InMemoryIdempotencyStore
from ois.kernel.recovery import RecoveryBackoff, RecoveryPolicy
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import ExecutionStatus, FailureClass, InvocationStatus


def make_context() -> ExecutionContext:
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="conformance"),
        objective="P0 recovery conformance",
    )


def test_rc01_timeout_is_bounded_retry() -> None:
    policy = RecoveryPolicy(max_retries=2)
    context = make_context()

    decision = policy.apply(context, FailureClass.TRANSIENT)

    assert decision.action == "retry"
    assert decision.retry_allowed is True
    assert context.retry_count == 1
    assert context.status == ExecutionStatus.RECOVERING


def test_rc02_transient_tool_failure_retries_then_succeeds() -> None:
    policy = RecoveryPolicy(max_retries=2)
    context = make_context()

    first = policy.apply(context, FailureClass.TRANSIENT)
    assert first.action == "retry"

    context.set_status(ExecutionStatus.EXECUTING)
    second = policy.classify(FailureClass.TRANSIENT, context)
    assert second.action == "retry"
    assert second.retry_allowed is True


def test_rc03_tool_failure_selects_fallback_without_retry() -> None:
    decision = RecoveryPolicy().apply(make_context(), FailureClass.TOOL)

    assert decision.action == "fallback"
    assert decision.retry_allowed is False
    assert decision.terminal is False


def test_rc04_invalid_output_requires_correction_path() -> None:
    context = make_context()
    decision = RecoveryPolicy().apply(context, FailureClass.PARAMETER)

    assert decision.action == "correct"
    assert decision.retry_allowed is False
    assert context.status == ExecutionStatus.RECEIVED


def test_rc05_permission_denial_never_retries() -> None:
    decision = RecoveryPolicy().apply(make_context(), FailureClass.PERMISSION)

    assert decision.action == "escalate"
    assert decision.retry_allowed is False
    assert decision.terminal is False


def test_rc06_corrupt_checkpoint_is_detected(tmp_path) -> None:
    context = make_context()
    store = JsonFileCheckpointStore(str(tmp_path))
    store.save(context)
    path = tmp_path / f"{context.identity.execution_id}.json"
    envelope = json.loads(path.read_text())
    envelope["state"]["objective"] = "tampered"
    path.write_text(json.dumps(envelope))

    with pytest.raises(CheckpointError, match="integrity hash mismatch"):
        store.load(context.identity.execution_id)


def test_rc07_retry_exhaustion_is_terminal() -> None:
    policy = RecoveryPolicy(max_retries=1)
    context = make_context()
    policy.apply(context, FailureClass.TRANSIENT)
    context.set_status(ExecutionStatus.EXECUTING)

    decision = policy.apply(context, FailureClass.TRANSIENT)

    assert decision.action == "escalate"
    assert decision.terminal is True
    assert context.status == ExecutionStatus.ESCALATED


def test_rc08_duplicate_invocation_is_idempotent() -> None:
    store = InMemoryIdempotencyStore()
    result = InvocationResult(
        invocation_id="inv-1",
        capability_id="test.side_effect",
        status=InvocationStatus.SUCCEEDED,
        output={"committed": True},
    )
    store.put("inv-1", result)
    store.put(
        "inv-1",
        InvocationResult(
            invocation_id="inv-1",
            capability_id="test.side_effect",
            status=InvocationStatus.SUCCEEDED,
            output={"committed": False},
        ),
    )

    cached = store.get("inv-1")
    assert cached is not None
    assert cached.output == {"committed": True}


def test_rc09_cancellation_is_explicit_and_terminal() -> None:
    token = CancellationToken()
    token.cancel("operator requested cancellation")

    assert token.cancelled is True
    with pytest.raises(ExecutionCancellation, match="operator requested cancellation"):
        token.raise_if_cancelled()


def test_rc10_exponential_backoff_is_deterministic_and_bounded() -> None:
    backoff = RecoveryBackoff(base_seconds=1.0, max_seconds=5.0)

    assert [backoff.delay(i) for i in range(1, 6)] == [1.0, 2.0, 4.0, 5.0, 5.0]


def test_rc11_safety_failure_stops_without_retry() -> None:
    context = make_context()
    decision = RecoveryPolicy().apply(context, FailureClass.SAFETY)

    assert decision.action == "stop"
    assert decision.retry_allowed is False
    assert decision.terminal is True
    assert context.status == ExecutionStatus.STOPPED


def test_rc12_recovery_is_observable_with_causation_and_correlation() -> None:
    context = make_context()
    ledger = EvidenceLedger()
    failure = ledger.record(
        context.identity.execution_id,
        "recovery.failure",
        {"failure_class": FailureClass.TRANSIENT.value},
        correlation_id="corr-1",
    )
    recovery = ledger.record(
        context.identity.execution_id,
        "recovery.decision",
        {"action": "retry"},
        correlation_id="corr-1",
        causation_id=str(failure.event_id),
    )

    events = ledger.list(context.identity.execution_id)
    assert len(events) == 2
    assert recovery.correlation_id == "corr-1"
    assert recovery.causation_id == str(failure.event_id)

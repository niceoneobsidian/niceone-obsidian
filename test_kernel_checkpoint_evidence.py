import pytest

from ois.kernel import (
    ExecutionContext,
    ExecutionIdentity,
    ExecutionStatus,
    InMemoryCheckpointStore,
)
from ois.kernel.checkpoint import CheckpointNotFound
from ois.kernel.evidence import EvidenceLedger


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="default"),
        objective="Checkpoint test",
    )


def test_checkpoint_save_and_restore():
    store = InMemoryCheckpointStore()
    context = make_context()

    context.working_memory["value"] = "original"

    store.save(context)

    execution_id = context.identity.execution_id

    assert store.exists(execution_id) is True

    restored = store.load(execution_id)

    assert restored.identity.execution_id == execution_id
    assert restored.objective == "Checkpoint test"
    assert restored.working_memory["value"] == "original"


def test_checkpoint_load_returns_independent_copy():
    store = InMemoryCheckpointStore()
    context = make_context()

    context.working_memory["value"] = "original"
    store.save(context)

    execution_id = context.identity.execution_id

    restored = store.load(execution_id)
    restored.working_memory["value"] = "modified"

    again = store.load(execution_id)

    assert again.working_memory["value"] == "original"


def test_checkpoint_preserves_execution_status():
    store = InMemoryCheckpointStore()
    context = make_context()

    context.set_status(ExecutionStatus.EXECUTING)
    store.save(context)

    restored = store.load(context.identity.execution_id)

    assert restored.status == ExecutionStatus.EXECUTING


def test_checkpoint_snapshot_contains_expected_representation():
    store = InMemoryCheckpointStore()
    context = make_context()

    store.save(context)

    snapshot = store.snapshot(context.identity.execution_id)

    assert snapshot["execution_id"] == str(context.identity.execution_id)
    assert snapshot["status"] == "received"
    assert "created_at" in snapshot
    assert "updated_at" in snapshot
    assert "state" in snapshot


def test_checkpoint_delete_removes_checkpoint():
    store = InMemoryCheckpointStore()
    context = make_context()

    execution_id = context.identity.execution_id

    store.save(context)
    store.delete(execution_id)

    assert store.exists(execution_id) is False

    with pytest.raises(CheckpointNotFound):
        store.load(execution_id)


def test_missing_checkpoint_snapshot_raises():
    store = InMemoryCheckpointStore()
    execution_id = ExecutionIdentity(tenant_id="default").execution_id

    with pytest.raises(CheckpointNotFound):
        store.snapshot(execution_id)


def test_evidence_record_preserves_event_relationships():
    ledger = EvidenceLedger()

    execution_id = ExecutionIdentity(tenant_id="default").execution_id

    event1 = ledger.record(
        execution_id=execution_id,
        event_type="execution.started",
        data={"objective": "Checkpoint test"},
        actor="test",
        component="test.kernel",
    )

    event2 = ledger.record(
        execution_id=execution_id,
        event_type="execution.completed",
        data={"status": "completed"},
        correlation_id=str(event1.event_id),
        causation_id=str(event1.event_id),
    )

    assert event1.execution_id == execution_id
    assert event1.event_type == "execution.started"
    assert event1.actor == "test"
    assert event1.component == "test.kernel"

    assert event2.correlation_id == str(event1.event_id)
    assert event2.causation_id == str(event1.event_id)


def test_evidence_ledger_is_append_only_and_ordered():
    ledger = EvidenceLedger()

    execution_id = ExecutionIdentity(tenant_id="default").execution_id

    event1 = ledger.record(
        execution_id=execution_id,
        event_type="execution.started",
        data={},
    )

    event2 = ledger.record(
        execution_id=execution_id,
        event_type="execution.completed",
        data={},
    )

    events = ledger.list(execution_id)

    assert len(events) == 2
    assert events[0].event_id == event1.event_id
    assert events[1].event_id == event2.event_id


def test_evidence_filters_by_execution():
    ledger = EvidenceLedger()

    execution_id = ExecutionIdentity(tenant_id="default").execution_id

    other_execution = ExecutionIdentity(tenant_id="default").execution_id

    ledger.record(
        execution_id=execution_id,
        event_type="execution.started",
        data={},
    )

    assert ledger.list(other_execution) == ()


def test_evidence_counts_match_events():
    ledger = EvidenceLedger()

    execution_id = ExecutionIdentity(tenant_id="default").execution_id

    other_execution = ExecutionIdentity(tenant_id="default").execution_id

    ledger.record(
        execution_id=execution_id,
        event_type="execution.started",
        data={},
    )

    ledger.record(
        execution_id=execution_id,
        event_type="execution.completed",
        data={},
    )

    assert ledger.count(execution_id) == 2
    assert ledger.count(other_execution) == 0
    assert ledger.count() == 2


def test_evidence_event_serialization_is_json_friendly():
    ledger = EvidenceLedger()

    execution_id = ExecutionIdentity(tenant_id="default").execution_id

    event = ledger.record(
        execution_id=execution_id,
        event_type="execution.started",
        data={},
    )

    serialized = event.to_dict()

    assert isinstance(serialized["event_id"], str)
    assert isinstance(serialized["execution_id"], str)
    assert isinstance(serialized["timestamp"], str)
    assert serialized["event_type"] == "execution.started"

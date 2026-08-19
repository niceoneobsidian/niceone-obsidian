from ois.kernel import (
    ExecutionContext,
    ExecutionIdentity,
    ExecutionStatus,
    InMemoryCheckpointStore,
)
from ois.kernel.checkpoint import CheckpointNotFound
from ois.kernel.evidence import EvidenceLedger


# =========================
# CHECKPOINT TESTS
# =========================

store = InMemoryCheckpointStore()

context = ExecutionContext(
    identity=ExecutionIdentity(tenant_id="default"),
    objective="Checkpoint test",
)

context.working_memory["value"] = "original"

store.save(context)

execution_id = context.identity.execution_id

assert store.exists(execution_id) is True

restored = store.load(execution_id)

assert restored.identity.execution_id == execution_id
assert restored.objective == "Checkpoint test"
assert restored.working_memory["value"] == "original"


# Verify load returns an independent copy.
restored.working_memory["value"] = "modified"

again = store.load(execution_id)

assert again.working_memory["value"] == "original"


# Verify status survives checkpointing.
context.set_status(ExecutionStatus.EXECUTING)
store.save(context)

restored = store.load(execution_id)

assert restored.status == ExecutionStatus.EXECUTING


# Verify snapshot contains the expected checkpoint representation.
snapshot = store.snapshot(execution_id)

assert snapshot["execution_id"] == str(execution_id)
assert snapshot["status"] == "executing"
assert "created_at" in snapshot
assert "updated_at" in snapshot
assert "state" in snapshot


# Verify deletion.
store.delete(execution_id)

assert store.exists(execution_id) is False

try:
    store.load(execution_id)
    raise AssertionError("Deleted checkpoint should not be loadable")
except CheckpointNotFound:
    pass


# Missing checkpoint should also raise.
try:
    store.snapshot(execution_id)
    raise AssertionError("Missing checkpoint snapshot should fail")
except CheckpointNotFound:
    pass


# =========================
# EVIDENCE TESTS
# =========================

ledger = EvidenceLedger()

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


# Ledger is append-only and preserves insertion order.
events = ledger.list(execution_id)

assert len(events) == 2
assert events[0].event_id == event1.event_id
assert events[1].event_id == event2.event_id


# Filtering by another execution should return nothing.
other_execution = ExecutionIdentity(
    tenant_id="default"
).execution_id

assert ledger.list(other_execution) == ()


# Count must agree with list.
assert ledger.count(execution_id) == 2
assert ledger.count(other_execution) == 0
assert ledger.count() == 2


# Event serialization must produce JSON-friendly identifiers/timestamp.
serialized = event1.to_dict()

assert isinstance(serialized["event_id"], str)
assert isinstance(serialized["execution_id"], str)
assert isinstance(serialized["timestamp"], str)
assert serialized["event_type"] == "execution.started"


print("KERNEL CHECKPOINT/EVIDENCE TEST: PASS")

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from ois.kernel import (
    ExecutionContext,
    ExecutionIdentity,
    EvidenceLedger,
    ExecutionRuntime,
    InvocationResult,
    InvocationStatus,
    LeaseLost,
    LeaseUnavailable,
    PostgreSQLCheckpointStore,
    PostgreSQLExecutionCoordinator,
    PostgreSQLIdempotencyStore,
    PostgreSQLSideEffectFencer,
)


DSN = os.getenv("OIS_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="OIS_POSTGRES_DSN is required for DE-03 integration tests")


def context():
    return ExecutionContext(
        identity=ExecutionIdentity(execution_id=uuid4(), tenant_id="de03-test"),
        objective="DE-03 fencing conformance",
    )


def result(invocation_id: str) -> InvocationResult:
    return InvocationResult(
        invocation_id=invocation_id,
        capability_id="test.capability",
        status=InvocationStatus.SUCCEEDED,
        output={"ok": True},
    )


def stores():
    assert DSN
    checkpoint = PostgreSQLCheckpointStore(DSN)
    idempotency = PostgreSQLIdempotencyStore(DSN)
    coordinator = PostgreSQLExecutionCoordinator(DSN)
    return checkpoint, idempotency, coordinator


def test_stale_worker_cannot_checkpoint_after_takeover() -> None:
    checkpoint, _, coordinator = stores()
    execution = context()

    stale = coordinator.claim(execution.identity.execution_id, execution.identity.tenant_id, "worker-a", ttl_seconds=-1)
    current = coordinator.claim(execution.identity.execution_id, execution.identity.tenant_id, "worker-b", ttl_seconds=30)

    assert current.lease_epoch > stale.lease_epoch

    with pytest.raises(LeaseLost):
        checkpoint.save_fenced(execution, stale)

    execution.working_memory["winner"] = "worker-b"
    checkpoint.save_fenced(execution, current)
    assert checkpoint.load(execution.identity.execution_id).working_memory["winner"] == "worker-b"


def test_stale_worker_cannot_record_idempotency() -> None:
    _, idempotency, coordinator = stores()
    execution = context()
    stale = coordinator.claim(execution.identity.execution_id, execution.identity.tenant_id, "worker-a", ttl_seconds=-1)
    current = coordinator.claim(execution.identity.execution_id, execution.identity.tenant_id, "worker-b", ttl_seconds=30)
    invocation_id = str(uuid4())

    with pytest.raises(LeaseLost):
        idempotency.put_fenced(invocation_id, result(invocation_id), stale)

    assert idempotency.put_fenced(invocation_id, result(invocation_id), current)
    assert idempotency.get(invocation_id) is not None


def test_concurrent_takeover_has_one_live_owner() -> None:
    assert DSN
    coordinator = PostgreSQLExecutionCoordinator(DSN)
    execution_id = uuid4()
    tenant_id = "de03-test"

    def claim(worker: str):
        try:
            return (worker, coordinator.claim(execution_id, tenant_id, worker, ttl_seconds=30), None)
        except LeaseUnavailable as exc:
            return (worker, None, exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ("worker-a", "worker-b")))

    winners = [item for item in results if item[1] is not None]
    losers = [item for item in results if item[2] is not None]
    assert len(winners) == 1
    assert len(losers) == 1
    assert winners[0][1].lease_epoch == 1


def test_crash_recovery_uses_new_epoch() -> None:
    checkpoint, _, coordinator = stores()
    execution = context()

    first = coordinator.claim(execution.identity.execution_id, execution.identity.tenant_id, "worker-a", ttl_seconds=30)
    execution.working_memory["checkpoint"] = "before-crash"
    checkpoint.save_fenced(execution, first)

    recovered = coordinator.claim(execution.identity.execution_id, execution.identity.tenant_id, "worker-b", ttl_seconds=30)
    assert recovered.lease_epoch == first.lease_epoch + 1

    restored = checkpoint.load(execution.identity.execution_id)
    restored.working_memory["recovered_by"] = "worker-b"
    checkpoint.save_fenced(restored, recovered)
    assert checkpoint.load(execution.identity.execution_id).working_memory["recovered_by"] == "worker-b"


def test_fenced_side_effect_completion_rejects_stale_epoch() -> None:
    assert DSN
    coordinator = PostgreSQLExecutionCoordinator(DSN)
    fencer = PostgreSQLSideEffectFencer(DSN)
    execution_id = uuid4()
    effect_id = f"de03-{uuid4()}"

    with coordinator._connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ois_side_effect_outbox (
                effect_id TEXT PRIMARY KEY,
                execution_id UUID NOT NULL,
                status TEXT NOT NULL,
                locked_at TIMESTAMPTZ,
                worker_id TEXT,
                worker_epoch BIGINT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cursor.execute(
            "INSERT INTO ois_side_effect_outbox (effect_id, execution_id, status) VALUES (%s, %s, 'PENDING')",
            (effect_id, execution_id),
        )

    stale = coordinator.claim(execution_id, "de03-test", "worker-a", ttl_seconds=-1)
    current = coordinator.claim(execution_id, "de03-test", "worker-b", ttl_seconds=30)

    with pytest.raises(LeaseLost):
        fencer.claim(effect_id, stale)

    assert fencer.claim(effect_id, current)
    assert fencer.complete(effect_id, current)


def test_runtime_records_fencing_rejection() -> None:
    evidence = EvidenceLedger()
    runtime = ExecutionRuntime(object(), object(), evidence)
    execution = context()
    lease = type("Lease", (), {
        "execution_id": execution.identity.execution_id,
        "worker_id": "worker-stale",
        "lease_epoch": 41,
    })()

    runtime._record_fencing_rejection(lease, "checkpoint")

    events = evidence.list(execution.identity.execution_id)
    assert events[-1].event_type == "execution.fencing_rejected"
    assert events[-1].data["operation"] == "checkpoint"
    assert events[-1].data["lease_epoch"] == 41

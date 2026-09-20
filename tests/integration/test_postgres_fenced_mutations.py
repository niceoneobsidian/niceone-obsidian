from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import psycopg
import pytest

from ois.infrastructure.postgres_fencing import (
    FencedPostgresDurableExecutionStore,
    FencingError,
    PostgresWorkerLeaseStore,
)
from ois.kernel.contracts import InvocationResult
from ois.kernel.postgres import PostgresDurableExecutionStore
from ois.kernel.side_effects import (
    SideEffectCommand,
    SideEffectResult,
    TransactionalSideEffectBoundary,
)
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import InvocationStatus


EXECUTION_ID = UUID("00000000-0000-0000-0000-000000000302")


def fencing_for(dsn: str) -> PostgresWorkerLeaseStore:
    return PostgresWorkerLeaseStore(lambda: psycopg.connect(dsn), ttl_seconds=30)


def clear(dsn: str) -> None:
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM ois_worker_leases WHERE execution_id = %s", (EXECUTION_ID,))
        cursor.execute("DELETE FROM ois_execution_checkpoints WHERE execution_id = %s", (EXECUTION_ID,))
        cursor.execute("DELETE FROM ois_idempotency_results WHERE execution_id = %s", (EXECUTION_ID,))
        cursor.execute("DELETE FROM ois_side_effect_outbox WHERE execution_id = %s", (EXECUTION_ID,))


def test_stale_epoch_rejects_checkpoint_mutation(migrated_postgres: str) -> None:
    clear(migrated_postgres)
    fencing = fencing_for(migrated_postgres)
    stale = fencing.claim(EXECUTION_ID, "worker-a")
    assert stale is not None
    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE ois_worker_leases SET lease_expires_at = now() - interval '1 second' "
            "WHERE execution_id = %s",
            (EXECUTION_ID,),
        )
    current = fencing.claim(EXECUTION_ID, "worker-b")
    assert current is not None

    base = PostgresDurableExecutionStore(lambda: psycopg.connect(migrated_postgres))
    context = ExecutionContext(
        identity=ExecutionIdentity(execution_id=EXECUTION_ID, tenant_id="tenant"),
        objective="fenced",
    )
    with pytest.raises(FencingError):
        FencedPostgresDurableExecutionStore(base, fencing, stale).save(context)

    FencedPostgresDurableExecutionStore(base, fencing, current).save(context)
    assert base.load(EXECUTION_ID).objective == "fenced"


def test_stale_epoch_rejects_idempotency_mutation(migrated_postgres: str) -> None:
    clear(migrated_postgres)
    fencing = fencing_for(migrated_postgres)
    stale = fencing.claim(EXECUTION_ID, "worker-a")
    assert stale is not None
    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE ois_worker_leases SET lease_expires_at = now() - interval '1 second' "
            "WHERE execution_id = %s",
            (EXECUTION_ID,),
        )
    current = fencing.claim(EXECUTION_ID, "worker-b")
    assert current is not None

    base = PostgresDurableExecutionStore(lambda: psycopg.connect(migrated_postgres))
    result = InvocationResult(
        invocation_id="fenced-invocation-1",
        capability_id="capability.test",
        status=InvocationStatus.SUCCEEDED,
        output={"ok": True},
    )
    with pytest.raises(FencingError):
        FencedPostgresDurableExecutionStore(base, fencing, stale).put_idempotency(
            "fenced-invocation-1", EXECUTION_ID, "tenant", result
        )

    FencedPostgresDurableExecutionStore(base, fencing, current).put_idempotency(
        "fenced-invocation-1", EXECUTION_ID, "tenant", result
    )
    assert base.get_idempotency("fenced-invocation-1") is not None


def test_stale_epoch_rejects_side_effect_completion(migrated_postgres: str) -> None:
    clear(migrated_postgres)
    fencing = fencing_for(migrated_postgres)
    stale = fencing.claim(EXECUTION_ID, "worker-a")
    assert stale is not None
    boundary = TransactionalSideEffectBoundary(lambda: psycopg.connect(migrated_postgres))
    command = boundary.enqueue(
        tenant_id="tenant",
        execution_id=EXECUTION_ID,
        invocation_id="fenced-effect-1",
        capability_id="capability.test",
        idempotency_key="fenced-effect-key-1",
        request={"value": 1},
        effect_id="fenced-effect-1",
    )
    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE ois_worker_leases SET lease_expires_at = now() - interval '1 second' "
            "WHERE execution_id = %s",
            (EXECUTION_ID,),
        )
    current = fencing.claim(EXECUTION_ID, "worker-b")
    assert current is not None
    result = SideEffectResult(
        effect_id=command.effect_id,
        idempotency_key=command.idempotency_key,
        output={"done": True},
        completed_at=datetime.now(UTC),
    )
    with pytest.raises(FencingError):
        boundary.complete(command, result, fencing=fencing, worker_lease=stale)

    boundary.complete(command, result, fencing=fencing, worker_lease=current)
    row = boundary.get_outbox_effect(command.effect_id)
    assert row is not None
    assert row["status"] == "COMPLETED"


def test_runtime_requires_current_worker_lease_when_fencing_enabled() -> None:
    # Runtime integration is enforced at its mutation boundary; a lease is mandatory.
    from ois.kernel.runtime import ExecutionError, ExecutionRuntime

    class NoopRegistry:
        def get(self, capability_id, version):
            raise AssertionError("execution should fail before capability lookup")

    runtime = ExecutionRuntime(
        registry=NoopRegistry(),
        checkpoint_store=type("Store", (), {})(),
        fencing=type("Fence", (), {"assert_current": lambda self, lease: None})(),
    )
    context = ExecutionContext(
        identity=ExecutionIdentity(execution_id=EXECUTION_ID),
        objective="lease-required",
    )
    with pytest.raises(ExecutionError, match="worker lease"):
        runtime.execute(context, "capability.test", "1", {}, invocation_id="inv-lease")

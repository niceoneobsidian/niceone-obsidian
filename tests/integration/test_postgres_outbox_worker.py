from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg

from ois.kernel.side_effects import (
    SideEffectResult,
    TransactionalSideEffectBoundary,
)


def boundary_for(dsn: str) -> TransactionalSideEffectBoundary:
    return TransactionalSideEffectBoundary(lambda: psycopg.connect(dsn))


def enqueue_one(
    boundary: TransactionalSideEffectBoundary,
    *,
    effect_id: str,
    invocation_id: str,
    idempotency_key: str,
) -> None:
    boundary.enqueue(
        tenant_id="tenant-conformance",
        execution_id=UUID("00000000-0000-0000-0000-000000000101"),
        invocation_id=invocation_id,
        capability_id="capability.publish",
        idempotency_key=idempotency_key,
        request={"payload": effect_id},
        effect_id=effect_id,
    )


def test_outbox_claim_is_exclusive_across_workers(
    migrated_postgres: str,
) -> None:
    """Two workers cannot claim the same pending effect concurrently."""
    setup = boundary_for(migrated_postgres)
    enqueue_one(
        setup,
        effect_id="effect-exclusive-1",
        invocation_id="invocation-exclusive-1",
        idempotency_key="idempotency-exclusive-1",
    )

    def claim() -> object:
        return boundary_for(migrated_postgres).claim(worker_id=str(uuid4()))

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = [future.result() for future in (executor.submit(claim), executor.submit(claim))]

    assert (first is None) != (second is None)
    command = first or second
    assert command is not None
    assert command.effect_id == "effect-exclusive-1"
    assert command.idempotency_key == "idempotency-exclusive-1"


def test_completed_outbox_effect_is_not_redelivered(
    migrated_postgres: str,
) -> None:
    boundary = boundary_for(migrated_postgres)
    enqueue_one(
        boundary,
        effect_id="effect-completed-1",
        invocation_id="invocation-completed-1",
        idempotency_key="idempotency-completed-1",
    )

    command = boundary.claim(worker_id="worker-complete")
    assert command is not None
    boundary.complete(
        command,
        SideEffectResult(
            effect_id=command.effect_id,
            idempotency_key=command.idempotency_key,
            output={"published": True},
            completed_at=datetime.now(UTC),
        ),
    )

    assert boundary_for(migrated_postgres).claim(worker_id="worker-replay") is None

    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, result-&gt;&gt;'output' FROM ois_side_effect_outbox WHERE effect_id = %s",
            (command.effect_id,),
        )
        status, output = cursor.fetchone()

    assert status == "COMPLETED"
    assert output == "{\"published\": true}"


def test_failed_outbox_effect_is_retryable_with_attempt_recorded(
    migrated_postgres: str,
) -> None:
    boundary = boundary_for(migrated_postgres)
    enqueue_one(
        boundary,
        effect_id="effect-retry-1",
        invocation_id="invocation-retry-1",
        idempotency_key="idempotency-retry-1",
    )

    command = boundary.claim(worker_id="worker-fail")
    assert command is not None
    boundary.fail(command, {"code": "temporary"})

    retry = boundary.claim(worker_id="worker-retry")
    assert retry is not None
    assert retry.effect_id == command.effect_id
    assert retry.idempotency_key == command.idempotency_key

    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT attempts, status, last_error-&gt;&gt;'code' FROM ois_side_effect_outbox WHERE effect_id = %s",
            (command.effect_id,),
        )
        attempts, status, error_code = cursor.fetchone()

    assert attempts == 1
    assert status == "PROCESSING"
    assert error_code == "temporary"


def test_stale_processing_effect_is_recovered_after_restart(
    migrated_postgres: str,
) -> None:
    boundary = boundary_for(migrated_postgres)
    enqueue_one(
        boundary,
        effect_id="effect-restart-1",
        invocation_id="invocation-restart-1",
        idempotency_key="idempotency-restart-1",
    )

    command = boundary.claim(worker_id="worker-crashed")
    assert command is not None

    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE ois_side_effect_outbox SET locked_at = %s WHERE effect_id = %s",
            (datetime.now(UTC) - timedelta(minutes=10), command.effect_id),
        )

    assert boundary_for(migrated_postgres).recover_stale() == 1
    recovered = boundary_for(migrated_postgres).claim(worker_id="worker-restarted")
    assert recovered is not None
    assert recovered.effect_id == command.effect_id
    assert recovered.idempotency_key == command.idempotency_key

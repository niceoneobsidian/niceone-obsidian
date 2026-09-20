from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

import psycopg
import pytest

from ois.infrastructure.postgres_fencing import FencingError, PostgresWorkerLeaseStore


EXECUTION_ID = UUID("00000000-0000-0000-0000-000000000301")


def store_for(dsn: str) -> PostgresWorkerLeaseStore:
    return PostgresWorkerLeaseStore(lambda: psycopg.connect(dsn), ttl_seconds=30)


def clear_lease(dsn: str) -> None:
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM ois_worker_leases WHERE execution_id = %s",
            (EXECUTION_ID,),
        )


def test_first_claim_gets_epoch_one(migrated_postgres: str) -> None:
    clear_lease(migrated_postgres)
    store = store_for(migrated_postgres)
    lease = store.claim(EXECUTION_ID, "worker-a")
    assert lease is not None
    assert lease.epoch == 1
    assert lease.worker_id == "worker-a"


def test_concurrent_claim_has_single_owner_and_monotonic_takeover(
    migrated_postgres: str,
) -> None:
    clear_lease(migrated_postgres)
    store = store_for(migrated_postgres)
    first = store.claim(EXECUTION_ID, "worker-a")
    assert first is not None

    def claim(worker: str):
        return store_for(migrated_postgres).claim(EXECUTION_ID, worker)

    with ThreadPoolExecutor(max_workers=2) as executor:
        a, b = [future.result() for future in (
            executor.submit(claim, "worker-b"),
            executor.submit(claim, "worker-c"),
        )]
    assert a is None and b is None

    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE ois_worker_leases
            SET lease_expires_at = %s
            WHERE execution_id = %s
            """,
            (datetime.now(UTC) - timedelta(seconds=1), EXECUTION_ID),
        )

    takeover = store.claim(EXECUTION_ID, "worker-b")
    assert takeover is not None
    assert takeover.epoch == first.epoch + 1
    assert takeover.worker_id == "worker-b"


def test_stale_worker_is_fenced_from_mutation(migrated_postgres: str) -> None:
    clear_lease(migrated_postgres)
    store = store_for(migrated_postgres)
    stale = store.claim(EXECUTION_ID, "worker-a")
    assert stale is not None

    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE ois_worker_leases SET lease_expires_at = now() - interval '1 second' "
            "WHERE execution_id = %s",
            (EXECUTION_ID,),
        )

    current = store.claim(EXECUTION_ID, "worker-b")
    assert current is not None
    assert current.epoch == stale.epoch + 1

    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        with pytest.raises(FencingError):
            store.assert_current(stale)


def test_renew_preserves_epoch(migrated_postgres: str) -> None:
    clear_lease(migrated_postgres)
    store = store_for(migrated_postgres)
    lease = store.claim(EXECUTION_ID, "worker-a")
    assert lease is not None
    renewed = store.renew(lease)
    assert renewed.epoch == lease.epoch
    assert renewed.worker_id == lease.worker_id


def test_crashed_worker_cannot_reclaim_after_takeover(migrated_postgres: str) -> None:
    clear_lease(migrated_postgres)
    store = store_for(migrated_postgres)
    crashed = store.claim(EXECUTION_ID, "worker-crashed")
    assert crashed is not None

    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE ois_worker_leases SET lease_expires_at = now() - interval '1 second' "
            "WHERE execution_id = %s",
            (EXECUTION_ID,),
        )

    recovered = store.claim(EXECUTION_ID, "worker-recovered")
    assert recovered is not None
    assert recovered.epoch == crashed.epoch + 1
    with pytest.raises(FencingError):
        store.assert_current(crashed)
    store.assert_current(recovered)

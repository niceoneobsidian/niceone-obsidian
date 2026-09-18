from __future__ import annotations

import psycopg
import pytest

from ois.infrastructure.postgres_execution import PostgresExecutionStore


def store_for(dsn: str) -> PostgresExecutionStore:
    return PostgresExecutionStore(lambda: psycopg.connect(dsn))


def test_idempotency_claim_replay_and_completion(
    migrated_postgres: str,
) -> None:
    first = store_for(migrated_postgres)
    second = store_for(migrated_postgres)

    assert first.claim_idempotency(
        "invocation-1",
        "execution-1",
        "tenant-1",
        "capability-1",
        "fingerprint-a",
    )
    assert not second.claim_idempotency(
        "invocation-1",
        "execution-1",
        "tenant-1",
        "capability-1",
        "fingerprint-a",
    )
    assert second.get_idempotency_result("invocation-1") is None

    first.complete_idempotency("invocation-1", {"ok": True})
    assert second.get_idempotency_result("invocation-1") == {"ok": True}


def test_idempotency_rejects_fingerprint_reuse(
    migrated_postgres: str,
) -> None:
    store = store_for(migrated_postgres)
    assert store.claim_idempotency(
        "invocation-2",
        "execution-2",
        "tenant-1",
        "capability-1",
        "fingerprint-a",
    )

    with pytest.raises(ValueError, match="different request"):
        store.claim_idempotency(
            "invocation-2",
            "execution-2",
            "tenant-1",
            "capability-1",
            "fingerprint-b",
        )


def test_failed_idempotency_claim_can_be_released(
    migrated_postgres: str,
) -> None:
    store = store_for(migrated_postgres)
    assert store.claim_idempotency(
        "invocation-3",
        "execution-3",
        "tenant-1",
        "capability-1",
        "fingerprint-a",
    )
    store.release_idempotency("invocation-3")
    assert store.claim_idempotency(
        "invocation-3",
        "execution-3-retry",
        "tenant-1",
        "capability-1",
        "fingerprint-a",
    )

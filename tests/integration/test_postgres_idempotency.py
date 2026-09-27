from __future__ import annotations

import concurrent.futures

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

    # 1. Initial claim succeeds
    assert first.claim_idempotency(
        "invocation-1",
        "00000000-0000-0000-0000-000000000001",
        "tenant-1",
        "capability-1",
        "fingerprint-a",
    )
    # 2. Matching replay returns False
    assert not second.claim_idempotency(
        "invocation-1",
        "00000000-0000-0000-0000-000000000001",
        "tenant-1",
        "capability-1",
        "fingerprint-a",
    )
    # 3. Pending claim has no result yet
    assert second.get_idempotency_result("invocation-1") is None

    # 4. Once completed, durable result is visible to distinct connections
    first.complete_idempotency("invocation-1", {"ok": True})
    assert second.get_idempotency_result("invocation-1") == {"ok": True}


def test_idempotency_rejects_fingerprint_reuse(
    migrated_postgres: str,
) -> None:
    store = store_for(migrated_postgres)
    assert store.claim_idempotency(
        "invocation-2",
        "00000000-0000-0000-0000-000000000002",
        "tenant-1",
        "capability-1",
        "fingerprint-a",
    )

    with pytest.raises(ValueError, match="different request"):
        store.claim_idempotency(
            "invocation-2",
            "00000000-0000-0000-0000-000000000002",
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
        "00000000-0000-0000-0000-000000000003",
        "tenant-1",
        "capability-1",
        "fingerprint-a",
    )
    store.release_idempotency("invocation-3")
    assert store.claim_idempotency(
        "invocation-3",
        "00000000-0000-0000-0000-000000000004",
        "tenant-1",
        "capability-1",
        "fingerprint-a",
    )


def test_concurrent_idempotency_claims_only_one_winner(
    migrated_postgres: str,
) -> None:
    """Item 1: Prove concurrent database connections race and produce exactly 1 winner."""
    invocation_id = "concurrent-inv-1"
    execution_id = "00000000-0000-0000-0000-000000000005"
    results: list[bool] = []

    def attempt_claim(worker_id: int) -> bool:
        store = store_for(migrated_postgres)
        return store.claim_idempotency(
            invocation_id=invocation_id,
            execution_id=execution_id,
            tenant_id="tenant-concurrency",
            capability_id="cap-1",
            request_fingerprint="fingerprint-concurrent",
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(attempt_claim, i) for i in range(5)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # Exactly one connection gets True (the winner), remaining 4 get False (replays)
    assert results.count(True) == 1
    assert results.count(False) == 4


def test_atomic_claim_and_outbox_staging(
    migrated_postgres: str,
) -> None:
    """Item 2 & 4: Claim and outbox entry stage atomically; re-claim stages no extra outbox."""
    store = store_for(migrated_postgres)
    inv_id = "atomic-inv-1"
    exec_id = "00000000-0000-0000-0000-000000000006"
    eff_id = "outbox-eff-1"

    # First call: claims and stages outbox
    claimed = store.claim_and_stage_outbox(
        invocation_id=inv_id,
        execution_id=exec_id,
        tenant_id="tenant-1",
        capability_id="cap-http",
        request_fingerprint="fp-atomic-1",
        effect_id=eff_id,
        idempotency_key="outbox-idem-1",
        request={"endpoint": "/publish", "payload": "data"},
    )
    assert claimed is True

    # Outbox effect exists and is PENDING
    outbox = store.get_outbox_effect(eff_id)
    assert outbox is not None
    assert outbox["status"] == "PENDING"
    assert outbox["request"]["endpoint"] == "/publish"

    # Second call with same invocation: replay returns False, does not overwrite outbox
    replay = store.claim_and_stage_outbox(
        invocation_id=inv_id,
        execution_id=exec_id,
        tenant_id="tenant-1",
        capability_id="cap-http",
        request_fingerprint="fp-atomic-1",
        effect_id="outbox-eff-2",  # Different effect ID
        idempotency_key="outbox-idem-2",
        request={"different": "request"},
    )
    assert replay is False
    # No second effect was staged
    assert store.get_outbox_effect("outbox-eff-2") is None


def test_failed_outbox_transaction_rolls_back_claim(
    migrated_postgres: str,
) -> None:
    """Item 5: If an error occurs before commit, neither claim nor outbox persists."""
    store = store_for(migrated_postgres)
    inv_id = "rollback-inv-1"
    exec_id = "00000000-0000-0000-0000-000000000007"

    with (
        pytest.raises(RuntimeError, match="simulated failure"),
        store.transaction() as conn,
    ):
        store.claim_idempotency(
            invocation_id=inv_id,
            execution_id=exec_id,
            tenant_id="tenant-1",
            capability_id="cap-1",
            request_fingerprint="fp-fail",
            connection=conn,
        )
        store.stage_side_effect(
            effect_id="eff-rollback-1",
            tenant_id="tenant-1",
            execution_id=exec_id,
            invocation_id=inv_id,
            capability_id="cap-1",
            idempotency_key="idem-fail",
            request={"step": 1},
            connection=conn,
        )
        # Simulated crash before commit
        raise RuntimeError("simulated failure")

    # Due to rollback, neither claim nor outbox exists
    assert store.get_idempotency_result(inv_id) is None
    assert store.get_outbox_effect("eff-rollback-1") is None

    # Invocation key can now be cleanly claimed by a new attempt
    retry_claimed = store.claim_idempotency(
        invocation_id=inv_id,
        execution_id=exec_id,
        tenant_id="tenant-1",
        capability_id="cap-1",
        request_fingerprint="fp-fail",
    )
    assert retry_claimed is True

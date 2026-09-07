from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import psycopg
import pytest

from ois.kernel.production_resilience import (
    FencingTokenMismatch,
    KernelPanicException,
    OISProductionResilience,
    RECOVERY_SCENARIO_IDS,
    RetryExhaustedException,
    validate_recovery_matrix,
    KernelTaskContext,
)


class AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False


class BrokenPool:
    def __init__(self):
        self.calls = 0

    def connection(self):
        self.calls += 1
        raise psycopg.OperationalError("database network split")


@pytest.mark.asyncio
async def test_rc04_bounds_retries_and_routes_to_separate_recovery_pool(monkeypatch):
    db_pool = BrokenPool()
    recovery_cur = AsyncMock()
    recovery_conn = AsyncMock()
    recovery_conn.cursor.return_value = AsyncContext(recovery_cur)
    recovery_pool = AsyncMock()
    recovery_pool.connection.return_value = AsyncContext(recovery_conn)

    redis_client = AsyncMock()
    redis_client.eval.side_effect = [
        [1, 7],
        [1, b"owner", 7],
        [0],
    ]

    kernel = OISProductionResilience(db_pool, redis_client, b"test-secret", recovery_pool=recovery_pool, lease_ttl_ms=100)
    kernel.evidence.append = AsyncMock()
    monkeypatch.setattr("ois.kernel.production_resilience.asyncio.sleep", AsyncMock())

    ctx = KernelTaskContext(
        tenant_id=str(uuid4()),
        thread_id="rc04-test",
        workflow_version="1",
        max_retries=2,
        base_backoff_s=0.001,
        retry_deadline_s=5,
    )

    async def operation(cursor, fencing_token):
        raise AssertionError("operation must not run when connection acquisition fails")

    with pytest.raises(RetryExhaustedException):
        await kernel.execute_fenced_transaction(ctx, "RC-04", operation, {"state": "frozen"})

    assert db_pool.calls == 3
    assert recovery_pool.connection.called


@pytest.mark.asyncio
async def test_rc05_stale_owner_is_rejected_before_side_effect():
    db_pool = AsyncMock()
    redis_client = AsyncMock()
    redis_client.eval.side_effect = [
        [1, 11],
        [1, b"worker-2", 12],
        [0],
    ]

    kernel = OISProductionResilience(db_pool, redis_client, b"test-secret", lease_ttl_ms=100)
    kernel.evidence.append = AsyncMock()

    ctx = KernelTaskContext(
        tenant_id=str(uuid4()),
        thread_id="rc05-test",
        workflow_version="1",
    )
    operation = AsyncMock()

    with pytest.raises(FencingTokenMismatch):
        await kernel.execute_fenced_transaction(ctx, "RC-05", operation, {})

    operation.assert_not_awaited()


@pytest.mark.asyncio
async def test_rc05_release_cannot_delete_new_owner_lock():
    db_pool = AsyncMock()
    redis_client = AsyncMock()
    redis_client.eval.side_effect = [
        [1, 1],
        [0],
    ]
    kernel = OISProductionResilience(db_pool, redis_client, b"secret", lease_ttl_ms=100)
    lease = await kernel.leases.acquire("lease:test")
    await kernel.leases.release(lease)
    assert redis_client.eval.call_count == 2


def test_recovery_matrix_contains_all_twelve_ids():
    assert RECOVERY_SCENARIO_IDS == tuple(f"RC-{index:02d}" for index in range(1, 13))


def test_recovery_matrix_fails_closed_when_handler_missing():
    handlers = {scenario_id: AsyncMock() for scenario_id in RECOVERY_SCENARIO_IDS[:-1]}
    with pytest.raises(KernelPanicException):
        validate_recovery_matrix(handlers)

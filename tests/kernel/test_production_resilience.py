from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import psycopg
import pytest

from ois.kernel.production_resilience import (
    RECOVERY_SCENARIO_IDS,
    FencingTokenMismatch,
    KernelPanicException,
    KernelTaskContext,
    OISProductionResilience,
    RetryExhaustedException,
    validate_recovery_matrix,
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


def test_rc04_bounds_retries_and_routes_to_separate_recovery_pool(monkeypatch):
    async def scenario():
        db_pool = BrokenPool()
        recovery_cur = AsyncMock()
        recovery_conn = MagicMock()
        recovery_conn.cursor.return_value = AsyncContext(recovery_cur)
        recovery_conn.commit = AsyncMock()
        recovery_pool = MagicMock()
        recovery_pool.connection.return_value = AsyncContext(recovery_conn)

        redis_client = AsyncMock()
        redis_client.eval.side_effect = [[1, 7], [0]]

        kernel = OISProductionResilience(
            db_pool,
            redis_client,
            b"test-secret",
            recovery_pool=recovery_pool,
            lease_ttl_ms=100,
        )
        kernel.evidence.append = AsyncMock()
        kernel.leases.assert_current = AsyncMock()
        monkeypatch.setattr("ois.kernel.production_resilience.LeaseHeartbeat._run", AsyncMock())

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
            await kernel.execute_fenced_transaction(
                ctx, "RC-04", operation, {"state": "frozen"}
            )

        assert db_pool.calls == 3
        assert recovery_pool.connection.called

    asyncio.run(scenario())


def test_rc05_stale_owner_is_rejected_before_side_effect():
    async def scenario():
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

    asyncio.run(scenario())


def test_rc05_release_is_conditional_on_nonce():
    async def scenario():
        db_pool = AsyncMock()
        redis_client = AsyncMock()
        redis_client.eval.side_effect = [[1, 1], [0]]
        kernel = OISProductionResilience(db_pool, redis_client, b"secret", lease_ttl_ms=100)
        lease = await kernel.leases.acquire("lease:test")
        await kernel.leases.release(lease)
        assert redis_client.eval.call_count == 2

    asyncio.run(scenario())


def test_recovery_matrix_contains_all_twelve_ids():
    assert tuple(f"RC-{index:02d}" for index in range(1, 13)) == RECOVERY_SCENARIO_IDS


def test_recovery_matrix_fails_closed_when_handler_missing():
    handlers = {scenario_id: AsyncMock() for scenario_id in RECOVERY_SCENARIO_IDS[:-1]}
    with pytest.raises(KernelPanicException):
        validate_recovery_matrix(handlers)

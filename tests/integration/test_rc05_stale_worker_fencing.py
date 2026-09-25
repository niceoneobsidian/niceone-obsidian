from __future__ import annotations

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
import redis.asyncio as redis
from psycopg_pool import AsyncConnectionPool

from ois.kernel.production_resilience import FencedLeaseManager

REDIS_DSN = os.getenv("OIS_TEST_REDIS_URL")
DB_DSN = os.getenv("OIS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest_asyncio.fixture
async def clients():
    if not REDIS_DSN or not DB_DSN:
        pytest.skip("OIS_TEST_REDIS_URL and OIS_TEST_DATABASE_URL are required")
    redis_client = redis.from_url(REDIS_DSN, decode_responses=False)
    pool = AsyncConnectionPool(DB_DSN, open=False, min_size=1, max_size=2)
    await pool.open()
    try:
        yield redis_client, pool
    finally:
        await pool.close()
        await redis_client.aclose()


async def test_stale_worker_fencing_blocks_postgres_mutation(clients) -> None:
    redis_client, pool = clients
    key = f"ois:test:fence:{uuid.uuid4()}"
    manager = FencedLeaseManager(redis_client, ttl_ms=200)

    first = await manager.acquire(key)
    await asyncio.sleep(0.25)
    second = await manager.acquire(key)

    assert second.fencing_token > first.fencing_token

    async with pool.connection() as conn:
        await conn.execute(
            "CREATE TEMP TABLE fencing_fixture "
            "(id integer primary key, active_fencing_token bigint not null, value text not null)"
        )
        await conn.execute(
            "INSERT INTO fencing_fixture (id, active_fencing_token, value) VALUES (1, %s, %s)",
            (second.fencing_token, "worker-2"),
        )

        stale = await conn.execute(
            "UPDATE fencing_fixture SET value = %s, active_fencing_token = %s "
            "WHERE id = 1 AND active_fencing_token <= %s",
            ("stale-worker-must-not-write", first.fencing_token, first.fencing_token),
        )
        assert stale.rowcount == 0

        current = await conn.execute(
            "UPDATE fencing_fixture SET value = %s, active_fencing_token = %s "
            "WHERE id = 1 AND active_fencing_token <= %s",
            ("current-worker-write", second.fencing_token, second.fencing_token),
        )
        assert current.rowcount == 1
        await conn.commit()

    await manager.release(second)

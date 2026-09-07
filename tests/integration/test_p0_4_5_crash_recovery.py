from __future__ import annotations

import asyncio
import json
import os
import uuid

import pytest
import redis.asyncio as redis

from ois.integration.redis_recovery import WorkerCrashRecoveryEngine

REDIS_DSN = os.getenv("OIS_TEST_REDIS_URL")
pytestmark = [pytest.mark.asyncio]


@pytest.mark.integration
async def test_stranded_message_is_reclaimed_and_processed() -> None:
    if not REDIS_DSN:
        pytest.skip("OIS_TEST_REDIS_URL is required for Redis integration tests")

    client = redis.from_url(REDIS_DSN, decode_responses=False)
    stream = f"ois:test:{uuid.uuid4()}"
    group = f"group:{uuid.uuid4()}"
    producer = WorkerCrashRecoveryEngine(client, stream=stream, group=group)
    await producer.initialize()
    try:
        message_id = await client.xadd(stream, {"task_context": json.dumps({"task_id": "crash-1"})})
        first = await client.xreadgroup(group, "dead-worker", {stream: ">"}, count=1, block=100)
        assert first and first[0][1][0][0] == message_id

        # Simulate worker death: message remains pending and is never ACKed.
        await asyncio.sleep(0.05)
        processed: list[dict[str, str]] = []
        engine = WorkerCrashRecoveryEngine(
            client,
            stream=stream,
            group=group,
            reclaim_consumer="recovery-worker",
        )
        count = await engine.recover_once(
            lambda task: _record(processed, task),
            min_idle_ms=1,
        )

        assert count == 1
        assert processed == [{"task_id": "crash-1"}]
        assert await client.xpending(stream, group) == 0
    finally:
        await client.xgroup_destroy(stream, group)
        await client.delete(stream)
        await client.aclose()


async def _record(target: list[dict[str, str]], task: dict[str, str]) -> None:
    target.append(task)

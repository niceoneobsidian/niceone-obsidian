from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as redis

from ois.integration.redis_recovery import WorkerCrashRecoveryEngine


class RedisKernelWorker:
    """Production worker entrypoint combining normal consumption and stale recovery."""

    def __init__(
        self,
        client: redis.Redis,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
        *,
        worker_id: str,
        stream: str = "ois:kernel:tasks",
        group: str = "kernel_workers",
    ) -> None:
        self.engine = WorkerCrashRecoveryEngine(
            client,
            stream=stream,
            group=group,
            reclaim_consumer=f"{worker_id}:recovery",
        )
        self.handler = handler
        self.worker_id = worker_id

    async def start(self, stop_event: asyncio.Event) -> None:
        await self.engine.initialize()
        while not stop_event.is_set():
            await self.engine.recover_once(self.handler, min_idle_ms=10_000)
            await self.engine.consume_once(self.worker_id, self.handler, block_ms=1_000)

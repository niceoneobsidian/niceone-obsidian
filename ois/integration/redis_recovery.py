from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as redis


TaskHandler = Callable[[dict[str, Any]], Awaitable[None]]


class WorkerCrashRecoveryEngine:
    """Durable Redis Streams worker with bounded stale-message reclamation.

    Delivery semantics are at-least-once. Handlers MUST be idempotent or use the
    OIS invocation/idempotency layer before performing external side effects.
    """

    def __init__(
        self,
        client: redis.Redis,
        *,
        stream: str = "ois:kernel:tasks",
        group: str = "kernel_workers",
        reclaim_consumer: str = "recovery-supervisor",
        max_retries: int = 3,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.redis = client
        self.stream = stream
        self.group = group
        self.reclaim_consumer = reclaim_consumer
        self.max_retries = max_retries

    async def initialize(self) -> None:
        try:
            await self.redis.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def consume_once(self, consumer: str, handler: TaskHandler, *, block_ms: int = 1000) -> bool:
        messages = await self.redis.xreadgroup(
            self.group,
            consumer,
            {self.stream: ">"},
            count=1,
            block=block_ms,
        )
        if not messages:
            return False

        _, entries = messages[0]
        message_id, payload = entries[0]
        task = self._decode(payload)
        await handler(task)
        await self.redis.xack(self.stream, self.group, message_id)
        # XDEL is deliberately after XACK; a crash between them leaves no lost work.
        await self.redis.xdel(self.stream, message_id)
        return True

    async def reclaim_stale(self, *, min_idle_ms: int = 10_000, count: int = 100) -> int:
        """Atomically transfer stale PEL entries and return the number claimed."""
        if min_idle_ms < 0:
            raise ValueError("min_idle_ms must be >= 0")

        claimed = 0
        cursor = "0-0"
        while True:
            cursor, entries, _ = await self.redis.xautoclaim(
                self.stream,
                self.group,
                self.reclaim_consumer,
                min_idle_ms,
                start_id=cursor,
                count=count,
            )
            claimed += len(entries)
            if cursor in {"0-0", b"0-0"} or not entries:
                break
        return claimed

    async def recover_once(
        self,
        handler: TaskHandler,
        *,
        min_idle_ms: int = 10_000,
        count: int = 100,
    ) -> int:
        """Claim stale messages, execute them, and ACK only after success."""
        cursor = "0-0"
        processed = 0
        while True:
            cursor, entries, _ = await self.redis.xautoclaim(
                self.stream,
                self.group,
                self.reclaim_consumer,
                min_idle_ms,
                start_id=cursor,
                count=count,
            )
            for message_id, payload in entries:
                task = self._decode(payload)
                try:
                    await handler(task)
                except Exception:
                    # Preserve PEL ownership for a later recovery pass.
                    continue
                await self.redis.xack(self.stream, self.group, message_id)
                await self.redis.xdel(self.stream, message_id)
                processed += 1
            if cursor in {"0-0", b"0-0"} or not entries:
                break
        return processed

    @staticmethod
    def _decode(payload: dict[Any, Any]) -> dict[str, Any]:
        raw = payload.get(b"task_context", payload.get("task_context"))
        if raw is None:
            raise ValueError("Redis task is missing task_context")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        task = json.loads(raw)
        if not isinstance(task, dict):
            raise ValueError("task_context must decode to a JSON object")
        return task


async def recovery_loop(
    engine: WorkerCrashRecoveryEngine,
    handler: TaskHandler,
    *,
    interval_seconds: float = 2.0,
    idle_ms: int = 10_000,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run recovery continuously until cancellation or an optional stop event."""
    while stop_event is None or not stop_event.is_set():
        await engine.recover_once(handler, min_idle_ms=idle_ms)
        await asyncio.sleep(interval_seconds)

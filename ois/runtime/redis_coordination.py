"""Redis-backed coordination primitives for horizontally scaled OIS workers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import redis


class RedisCoordination:
    """Small leased lock boundary; durable state remains in PostgreSQL."""

    def __init__(self, url: str, *, namespace: str = "ois") -> None:
        self.client = redis.Redis.from_url(url, decode_responses=True)
        self.namespace = namespace

    def ping(self) -> bool:
        return bool(self.client.ping())

    @contextmanager
    def lease(self, key: str, *, ttl_seconds: int = 30) -> Iterator[str]:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        lock = self.client.lock(
            f"{self.namespace}:lease:{key}",
            timeout=ttl_seconds,
            blocking_timeout=ttl_seconds,
        )
        token = str(uuid4())
        acquired = lock.acquire()
        if not acquired:
            raise TimeoutError(f"could not acquire Redis lease: {key}")
        try:
            yield token
        finally:
            try:
                lock.release()
            except redis.exceptions.LockError:
                # TTL expiry is an explicit recovery boundary; never mask the
                # completed work with a secondary lease-release failure.
                pass

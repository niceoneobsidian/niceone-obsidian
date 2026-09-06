from __future__ import annotations

import json
from uuid import uuid4

import redis


class RedisTransientCoordinator:
    """Redis coordination for execution locks, idempotency, and cancellation."""

    _RELEASE_LOCK_LUA = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    end
    return 0
    """

    _WRITE_IDEMPOTENCY_LUA = """
    if redis.call('exists', KEYS[1]) == 1 then
        return 0
    end
    redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2])
    return 1
    """

    def __init__(self, redis_url: str) -> None:
        self.client: redis.Redis[str] = redis.Redis.from_url(
            redis_url, decode_responses=True
        )

    def ping(self) -> bool:
        return bool(self.client.ping())

    def acquire_execution_lock(self, execution_id: str, lock_timeout_sec: int = 30) -> str | None:
        """Acquire an expiring lock and return an owner token, or ``None`` if held."""
        if lock_timeout_sec <= 0:
            raise ValueError("lock_timeout_sec must be positive")
        token = str(uuid4())
        acquired = self.client.set(
            f"ois:lock:{execution_id}", token, nx=True, ex=lock_timeout_sec
        )
        return token if acquired else None

    def release_execution_lock(self, execution_id: str, owner_token: str) -> bool:
        """Release only when the caller still owns the lock."""
        result = self.client.eval(
            self._RELEASE_LOCK_LUA, 1, f"ois:lock:{execution_id}", owner_token
        )
        return bool(result)

    def check_idempotency_cache(self, transaction_id: str) -> str | None:
        return self.client.get(f"ois:idempotency:{transaction_id}")

    def write_idempotency_cache(
        self, transaction_id: str, serialized_result: str, ttl_sec: int = 86_400
    ) -> bool:
        """Write once; duplicate writers cannot overwrite the first result."""
        if ttl_sec <= 0:
            raise ValueError("ttl_sec must be positive")
        result = self.client.eval(
            self._WRITE_IDEMPOTENCY_LUA,
            1,
            f"ois:idempotency:{transaction_id}",
            serialized_result,
            str(ttl_sec),
        )
        return bool(result)

    def cache_json_result(
        self, transaction_id: str, result: object, ttl_sec: int = 86_400
    ) -> bool:
        return self.write_idempotency_cache(
            transaction_id,
            json.dumps(result, sort_keys=True, separators=(",", ":")),
            ttl_sec,
        )

    def set_cancellation_signal(self, execution_id: str, ttl_sec: int = 300) -> None:
        if ttl_sec <= 0:
            raise ValueError("ttl_sec must be positive")
        self.client.set(f"ois:cancel:{execution_id}", "TRUE", ex=ttl_sec)

    def is_cancelled(self, execution_id: str) -> bool:
        return bool(self.client.exists(f"ois:cancel:{execution_id}"))

    def clear_cancellation_signal(self, execution_id: str) -> bool:
        return bool(self.client.delete(f"ois:cancel:{execution_id}"))

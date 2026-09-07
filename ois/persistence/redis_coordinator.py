from __future__ import annotations

import json
from uuid import uuid4

import redis

from ois.kernel.contracts import InvocationResult
from ois.kernel.types import InvocationStatus


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

    def set_cancellation_signal(
        self, execution_id: str, ttl_sec: int = 300, reason: str = "cancelled"
    ) -> None:
        if ttl_sec <= 0:
            raise ValueError("ttl_sec must be positive")
        self.client.set(
            f"ois:cancel:{execution_id}",
            json.dumps({"reason": reason}, sort_keys=True),
            ex=ttl_sec,
        )

    def is_cancelled(self, execution_id: str) -> bool:
        return bool(self.client.exists(f"ois:cancel:{execution_id}"))

    def cancellation_reason(self, execution_id: str) -> str | None:
        value = self.client.get(f"ois:cancel:{execution_id}")
        if value is None:
            return None
        try:
            return str(json.loads(value).get("reason"))
        except (TypeError, ValueError):
            return value

    def clear_cancellation_signal(self, execution_id: str) -> bool:
        return bool(self.client.delete(f"ois:cancel:{execution_id}"))


class RedisIdempotencyStore:
    """Durable runtime idempotency adapter backed by Redis write-once records."""

    def __init__(self, coordinator: RedisTransientCoordinator, ttl_sec: int = 86_400) -> None:
        self.coordinator = coordinator
        self.ttl_sec = ttl_sec

    def get(self, invocation_id: str) -> InvocationResult | None:
        cached = self.coordinator.check_idempotency_cache(invocation_id)
        if cached is None:
            return None
        data = json.loads(cached)
        return InvocationResult(
            invocation_id=data["invocation_id"],
            capability_id=data["capability_id"],
            status=InvocationStatus(data["status"]),
            output=data.get("output"),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )

    def put(self, invocation_id: str, result: InvocationResult) -> None:
        if result.status not in {InvocationStatus.SUCCEEDED, InvocationStatus.CANCELLED}:
            return
        payload = {
            "invocation_id": result.invocation_id,
            "capability_id": result.capability_id,
            "status": result.status.value,
            "output": result.output,
            "error": result.error,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "metadata": dict(result.metadata),
        }
        self.coordinator.cache_json_result(invocation_id, payload, self.ttl_sec)


class RedisCancellationToken:
    """Cross-process cancellation token consumed by the OIS runtime."""

    def __init__(self, coordinator: RedisTransientCoordinator, execution_id: str) -> None:
        self.coordinator = coordinator
        self.execution_id = execution_id

    @property
    def cancelled(self) -> bool:
        return self.coordinator.is_cancelled(self.execution_id)

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled

    @property
    def reason(self) -> str | None:
        return self.coordinator.cancellation_reason(self.execution_id)

    def cancel(self, reason: str | None = None) -> None:
        self.coordinator.set_cancellation_signal(
            self.execution_id, reason=reason or "cancelled"
        )

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            from ois.kernel.cancellation import ExecutionCancellation

            raise ExecutionCancellation(self.reason or "Execution cancelled.")

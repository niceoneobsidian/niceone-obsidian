"""Deterministic per-source rate limiting primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from time import monotonic


@dataclass(frozen=True)
class RateLimitPolicy:
    capacity: float
    refill_per_second: float

    def __post_init__(self) -> None:
        if self.capacity <= 0 or self.refill_per_second <= 0:
            raise ValueError("rate-limit capacity and refill must be positive")


@dataclass(frozen=True)
class RateLimitState:
    tokens: float
    observed_at: float


class TokenBucket:
    def __init__(self, policy: RateLimitPolicy, *, clock: Callable[[], float] = monotonic) -> None:
        self._policy = policy
        self._clock = clock
        self._state = RateLimitState(policy.capacity, clock())
        self._lock = RLock()

    def acquire(self, cost: float = 1.0) -> bool:
        if cost <= 0 or cost > self._policy.capacity:
            raise ValueError("cost must be > 0 and <= bucket capacity")
        with self._lock:
            now = self._clock()
            elapsed = max(0.0, now - self._state.observed_at)
            tokens = min(
                self._policy.capacity, self._state.tokens + elapsed * self._policy.refill_per_second
            )
            if tokens < cost:
                self._state = RateLimitState(tokens, now)
                return False
            self._state = RateLimitState(tokens - cost, now)
            return True

    def snapshot(self) -> RateLimitState:
        with self._lock:
            return self._state

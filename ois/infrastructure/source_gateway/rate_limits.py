"""Governed rate-limit manager built on the existing token-bucket primitive."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from .limits import RateLimitPolicy, RateLimitState, TokenBucket


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: float = 0.0
    key: str = ""


class RateLimitManager:
    """Tenant/source aware rate-limit coordinator.

    The manager owns buckets; TokenBucket remains the low-level deterministic
    primitive used by the SourceGateway.
    """

    def __init__(self, policies: dict[str, RateLimitPolicy] | None = None) -> None:
        self._policies = dict(policies or {})
        self._buckets: dict[str, TokenBucket] = {}
        self._last_denied: dict[str, float] = {}

    def configure(self, key: str, policy: RateLimitPolicy) -> None:
        self._policies[key] = policy
        self._buckets.pop(key, None)

    def _bucket(self, key: str) -> TokenBucket | None:
        policy = self._policies.get(key)
        if policy is None:
            return None
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(policy)
            self._buckets[key] = bucket
        return bucket

    def allow(self, key: str, *, cost: float = 1.0) -> RateLimitDecision:
        bucket = self._bucket(key)
        if bucket is None:
            return RateLimitDecision(True, key=key)
        if bucket.acquire(cost):
            self._last_denied.pop(key, None)
            return RateLimitDecision(True, key=key)
        now = monotonic()
        self._last_denied[key] = now
        state = bucket.snapshot()
        retry = max(0.0, (cost - state.tokens) / self._policies[key].refill_per_second)
        return RateLimitDecision(False, retry, key)

    def snapshot(self, key: str) -> RateLimitState | None:
        bucket = self._bucket(key)
        return bucket.snapshot() if bucket else None

    def policies(self) -> tuple[str, ...]:
        return tuple(sorted(self._policies))

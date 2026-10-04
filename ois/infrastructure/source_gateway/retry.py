"""Bounded retry/backoff policy for source acquisition failures."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    jitter_ratio: float = 0.2

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.base_delay_seconds <= 0 or self.max_delay_seconds <= 0:
            raise ValueError("retry delays must be positive")
        if self.base_delay_seconds > self.max_delay_seconds:
            raise ValueError("base delay cannot exceed max delay")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")


@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    attempt: int
    delay_seconds: float
    reason: str


class RetryController:
    """Pure, bounded retry decisions; sleeping remains owned by the scheduler."""

    def __init__(self, policy: RetryPolicy | None = None, *, seed: int = 0) -> None:
        self._policy = policy or RetryPolicy()
        self._random = Random(seed)

    @property
    def max_attempts(self) -> int:
        return self._policy.max_attempts

    def decide(
        self,
        *,
        attempt: int,
        retryable: bool,
        reason: str = "source_failure",
    ) -> RetryDecision:
        if attempt < 1:
            raise ValueError("attempt must be positive")
        if not retryable or attempt >= self._policy.max_attempts:
            return RetryDecision(False, attempt, 0.0, reason)

        exponential = min(
            self._policy.max_delay_seconds,
            self._policy.base_delay_seconds * (2 ** (attempt - 1)),
        )
        jitter = exponential * self._policy.jitter_ratio * self._random.random()
        return RetryDecision(
            True, attempt, min(self._policy.max_delay_seconds, exponential + jitter), reason
        )

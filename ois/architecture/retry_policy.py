"""22. Retry Policy Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class RetryPolicy(Contract):
    max_attempts: int = 1
    backoff_seconds: float = 0.0

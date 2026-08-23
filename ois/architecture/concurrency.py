"""19. Concurrency Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class ConcurrencyPolicy(Contract):
    max_parallel: int = 1
    timeout_seconds: float | None = None

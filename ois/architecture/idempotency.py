"""20. Idempotency Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class IdempotencyKey(Contract):
    key: str = ""

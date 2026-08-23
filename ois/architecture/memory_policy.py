"""41. Memory Policy Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class MemoryPolicy(Contract):
    retention_days: int | None = None
    scope: str = "default"

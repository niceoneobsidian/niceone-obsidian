"""32. Model Policy Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class ModelPolicy(Contract):
    quality_floor: float = 0.0
    max_latency_ms: int | None = None
    max_cost: float | None = None

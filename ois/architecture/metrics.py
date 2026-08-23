"""48. Metrics Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class MetricSample(Contract):
    name: str = ""
    value: float = 0.0
    unit: str = "1"

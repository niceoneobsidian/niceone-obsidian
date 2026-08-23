"""23. Fallback Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class FallbackPlan(Contract):
    targets: tuple[str, ...] = ()

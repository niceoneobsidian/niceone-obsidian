"""31. Model Adapter Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class ModelAdapterSpec(Contract):
    provider: str = ""
    operations: tuple[str, ...] = ()

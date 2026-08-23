"""33. Model Budget Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class ModelBudget(Contract):
    token_limit: int | None = None
    cost_limit: float | None = None

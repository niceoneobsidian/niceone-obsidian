"""49. Evaluation and Experiment Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class Experiment(Contract):
    baseline: str = ""
    candidate: str = ""
    evidence: tuple[str, ...] = ()
    decision: str = "pending"

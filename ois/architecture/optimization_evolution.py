"""50. Optimization and Controlled Evolution Plane."""
from dataclasses import dataclass
from enum import Enum
from .base import Contract

class EvolutionDecision(str, Enum):
    PENDING = "pending"; APPROVED = "approved"; REJECTED = "rejected"; ROLLBACK = "rollback"

@dataclass(frozen=True)
class EvolutionCandidate(Contract):
    evidence: tuple[str, ...] = ()
    decision: EvolutionDecision = EvolutionDecision.PENDING

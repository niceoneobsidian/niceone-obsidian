"""30. Agent Evaluation Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class AgentEvaluation(Contract):
    score: float = 0.0
    evidence: tuple[str, ...] = ()

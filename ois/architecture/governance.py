"""44. Governance Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class GovernanceDecision(Contract):
    subject: str = ""
    allowed: bool = False
    reason: str = ""

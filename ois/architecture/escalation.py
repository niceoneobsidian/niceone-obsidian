"""25. Escalation Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class EscalationRequest(Contract):
    reason: str = ""
    target: str = ""

"""28. Agent Delegation Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class DelegationRequest(Contract):
    sender: str = ""
    recipient: str = ""
    task: str = ""

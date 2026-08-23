"""43. Supervisor Decision Plane."""
from dataclasses import dataclass
from enum import Enum
from .base import Contract

class SupervisorAction(str, Enum):
    OBSERVE = "observe"; ALLOW = "allow"; PAUSE = "pause"; REDIRECT = "redirect"; RETRY = "retry"; ESCALATE = "escalate"; TERMINATE = "terminate"

@dataclass(frozen=True)
class SupervisorDecision(Contract):
    action: SupervisorAction = SupervisorAction.OBSERVE
    reason: str = ""

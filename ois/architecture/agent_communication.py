"""29. Agent Communication Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class AgentMessage(Contract):
    sender: str = ""
    recipient: str = ""
    intent: str = ""
    correlation_id: str = ""

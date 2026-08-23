"""27. Agent State Plane."""
from dataclasses import dataclass
from enum import Enum
from .base import Contract

class AgentState(str, Enum):
    INITIALIZED = "initialized"; PLANNING = "planning"; ACTING = "acting"; WAITING = "waiting"; PAUSED = "paused"; COMPLETED = "completed"; FAILED = "failed"

@dataclass(frozen=True)
class AgentStateRecord(Contract):
    state: AgentState = AgentState.INITIALIZED

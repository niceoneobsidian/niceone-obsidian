"""36. Workflow State Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class WorkflowState(Contract):
    status: str = "created"
    current_step: str | None = None

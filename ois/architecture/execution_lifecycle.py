"""17. Execution Lifecycle Plane."""

from dataclasses import dataclass
from enum import Enum

from .base import Contract


class ExecutionState(str, Enum):
    CREATED = "created"
    AUTHORIZED = "authorized"
    ROUTED = "routed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATED = "validated"


@dataclass(frozen=True)
class ExecutionLifecycle(Contract):
    state: ExecutionState = ExecutionState.CREATED

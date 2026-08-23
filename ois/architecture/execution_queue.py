"""18. Execution Queue Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class ExecutionQueueItem(Contract):
    request_id: str = ""
    priority: int = 0

"""37. Workflow Dependency Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class WorkflowDependency(Contract):
    upstream: str = ""
    downstream: str = ""

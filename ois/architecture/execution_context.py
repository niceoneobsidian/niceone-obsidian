"""16. Execution Context Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class ExecutionContext(Contract):
    request_id: str = ""
    tenant_id: str | None = None
    actor: str | None = None

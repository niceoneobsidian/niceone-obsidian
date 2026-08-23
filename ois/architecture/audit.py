"""45. Audit Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class AuditRecord(Contract):
    actor: str = ""
    action: str = ""
    target: str = ""
    outcome: str = ""
    timestamp: str = ""

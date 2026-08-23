"""Human oversight contracts."""
from dataclasses import dataclass

@dataclass(frozen=True)
class ApprovalRequest:
    action: str
    risk: str
    approver_scope: str

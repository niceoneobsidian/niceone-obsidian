"""Security architecture contracts."""
from dataclasses import dataclass

@dataclass(frozen=True)
class SecurityContext:
    principal: str
    resource: str
    action: str

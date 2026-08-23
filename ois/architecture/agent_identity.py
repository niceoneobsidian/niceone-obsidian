"""26. Agent Identity Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class AgentIdentity(Contract):
    owner: str | None = None
    permissions: tuple[str, ...] = ()

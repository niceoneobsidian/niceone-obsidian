"""46. Event Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class OISEvent(Contract):
    name: str = ""
    timestamp: str = ""
    attributes: tuple[tuple[str, str], ...] = ()

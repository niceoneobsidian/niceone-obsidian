"""24. Checkpoint Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class Checkpoint(Contract):
    execution_id: str = ""
    state: bytes = b""

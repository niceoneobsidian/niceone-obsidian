"""40. Provenance Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class ProvenanceRecord(Contract):
    source_ref: str = ""
    operation: str = ""
    timestamp: str = ""

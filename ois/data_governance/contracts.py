"""Data governance contracts."""
from dataclasses import dataclass

@dataclass(frozen=True)
class DataClassification:
    name: str
    retention_days: int
    owner: str

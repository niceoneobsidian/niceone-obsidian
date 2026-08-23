"""42. Memory Retrieval Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class MemoryQuery(Contract):
    query: str = ""
    limit: int = 10

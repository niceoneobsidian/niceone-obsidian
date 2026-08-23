"""39. Retrieval Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class RetrievalRequest(Contract):
    query: str = ""
    limit: int = 10

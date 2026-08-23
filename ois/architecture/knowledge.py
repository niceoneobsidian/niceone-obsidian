"""38. Knowledge Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class KnowledgeRecord(Contract):
    source: str = ""
    content_ref: str = ""

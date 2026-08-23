"""Release architecture contracts."""
from dataclasses import dataclass

@dataclass(frozen=True)
class ReleaseCandidate:
    version: str
    artifact: str
    channel: str

"""Software supply-chain security contracts."""
from dataclasses import dataclass

@dataclass(frozen=True)
class ArtifactProvenance:
    artifact: str
    source: str
    digest: str

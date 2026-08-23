"""Disaster recovery contracts."""
from dataclasses import dataclass

@dataclass(frozen=True)
class RecoveryPoint:
    resource: str
    checkpoint_id: str
    created_at: str

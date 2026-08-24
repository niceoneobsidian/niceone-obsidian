"""High availability contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FailureDomain:
    name: str
    healthy: bool
    capacity: int

"""Capability flag contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureFlag:
    name: str
    enabled: bool
    rollout: int = 0

"""Shared immutable contract primitives for architecture layers."""
from dataclasses import dataclass, field
from typing import Mapping

@dataclass(frozen=True)
class Contract:
    id: str
    version: str
    metadata: Mapping[str, object] = field(default_factory=dict)

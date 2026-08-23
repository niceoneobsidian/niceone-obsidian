"""Deployment architecture contracts."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Environment:
    name: str
    version: str
    immutable: bool = True

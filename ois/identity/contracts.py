"""Identity and access contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    id: str
    kind: str
    scope: str

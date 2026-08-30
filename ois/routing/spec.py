"""Routing contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RouteRequest:
    """Identity requirements used to select a registered object."""

    object_id: str
    version: str
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteResult:
    """Selected registered object and immutable identity."""

    object_id: str
    version: str
    value: object

"""Control-plane request contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ControlRequest:
    """Minimal request used to resolve a registered capability."""

    capability_id: str
    capability_version: str
    input: Mapping[str, object] = field(default_factory=dict)

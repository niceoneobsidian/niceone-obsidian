"""Control-plane request contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class ControlRequest:
    """Minimal request used to resolve a registered capability."""

    capability_id: str
    capability_version: str
    input: Mapping[str, object] = field(default_factory=dict)

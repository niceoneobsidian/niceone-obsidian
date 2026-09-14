"""Infrastructure-independent persistence ports."""

from __future__ import annotations

from collections.abc import Protocol
from typing import Any

from .state import ExecutionState


class EvidenceRepository(Protocol):
    def append(self, execution_id: str, category: str, payload: dict[str, Any]) -> None: ...


class ExecutionStateRepository(Protocol):
    def get(self, execution_id: str) -> ExecutionState | None: ...
    def transition(self, execution_id: str, state: ExecutionState) -> None: ...

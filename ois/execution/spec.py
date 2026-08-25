"""Execution contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExecutionRequest:
    object_id: str
    version: str
    input: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    output: object = None
    error: str | None = None

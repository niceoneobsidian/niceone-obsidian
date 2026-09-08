"""Stable contracts for the sovereign OIS control plane."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4


class ExecutionState(StrEnum):
    PROPOSED = "proposed"
    AUTHORIZED = "authorized"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ESCALATED = "escalated"


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Typed request crossing the OIS safety boundary."""

    capability: str
    input: dict[str, Any]
    workflow_id: str | None = None
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    actor: str = "system"
    tenant_id: str = "personal"
    risk: str = "normal"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    policy_version: str = "v1"


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    execution_id: str
    state: ExecutionState
    output: Any = None
    error: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


class ExecutionBackend(Protocol):
    """Provider-neutral execution interface owned by OIS."""

    name: str

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        ...


class ToolAdapter(Protocol):
    """Authorized external side-effect interface."""

    name: str

    def invoke(self, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

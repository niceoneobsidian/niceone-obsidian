from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from .state import ExecutionContext
from .types import (
    InvocationStatus,
    RiskLevel,
    SideEffectLevel,
)


@dataclass(frozen=True)
class CapabilityContract:
    capability_id: str
    version: str
    description: str

    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)

    risk_level: RiskLevel = RiskLevel.LOW
    permissions: tuple[str, ...] = ()
    allowed_domains: tuple[str, ...] = ()

    timeout_seconds: float = 30.0
    max_retries: int = 0

    side_effects: SideEffectLevel = SideEffectLevel.NONE
    idempotent: bool = True


@dataclass(frozen=True)
class AgentContract(CapabilityContract):
    required_tools: tuple[str, ...] = ()
    model_requirements: Mapping[str, Any] = field(default_factory=dict)
    max_iterations: int = 1


@dataclass(frozen=True)
class ToolContract(CapabilityContract):
    network_policy: Mapping[str, Any] = field(default_factory=dict)
    secrets_required: tuple[str, ...] = ()
    requires_approval: bool = False


class CancellationHandle(Protocol):
    def raise_if_cancelled(self) -> None:
        ...


@dataclass
class InvocationRequest:
    invocation_id: str
    capability_id: str
    input: Mapping[str, Any]

    execution: ExecutionContext

    timeout_seconds: float | None = None
    attempt: int = 0
    cancellation: CancellationHandle | None = None


@dataclass
class InvocationResult:
    invocation_id: str
    capability_id: str
    status: InvocationStatus

    output: Any = None
    error: Mapping[str, Any] | None = None

    started_at: str | None = None
    completed_at: str | None = None

    metadata: Mapping[str, Any] = field(default_factory=dict)


class Capability(Protocol):
    @property
    def contract(self) -> CapabilityContract:
        ...

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        ...


class PolicyEngine(Protocol):
    def authorize(
        self,
        request: InvocationRequest,
        contract: CapabilityContract,
    ) -> bool:
        ...


class Validator(Protocol):
    def validate_input(
        self,
        request: InvocationRequest,
        contract: CapabilityContract,
    ) -> None:
        ...

    def validate_output(
        self,
        result: InvocationResult,
        contract: CapabilityContract,
    ) -> None:
        ...

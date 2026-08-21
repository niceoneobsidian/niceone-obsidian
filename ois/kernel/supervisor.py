from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .contracts import InvocationResult, InvocationStatus
from .recovery import RecoveryDecision, RecoveryPolicy
from .registry import CapabilityNotFoundError


class SupervisorError(Exception):
    """Base supervisor error."""


class AgentSelectionError(SupervisorError):
    """Raised when an execution cannot be delegated to an agent."""


@dataclass(frozen=True)
class SupervisorRequest:
    objective: str
    capability_id: str
    version: str
    input_data: Dict[str, Any]
    invocation_id: str


@dataclass(frozen=True)
class SupervisionDecision:
    action: str
    reason: str
    terminal: bool


class Supervisor:
    """
    Deterministic governance/delegation layer above runtime orchestration.

    The Supervisor does not execute capabilities itself. It validates direct
    invocation requests and delegates either single-capability execution to
    the runtime or plan execution to the PlanOrchestrator.
    """

    def __init__(
        self,
        runtime: Any = None,
        *,
        agent_registry: Any = None,
        orchestrator: Any = None,
        recovery_policy: Optional[RecoveryPolicy] = None,
    ) -> None:
        self.runtime = runtime
        self.agent_registry = agent_registry
        self.orchestrator = orchestrator
        self.recovery_policy = recovery_policy or RecoveryPolicy()

    def select_agent(self, capability_id: str, version: str) -> Any:
        """Resolve an authorized agent contract from the AgentRegistry."""
        if self.agent_registry is None:
            raise AgentSelectionError("agent_registry is required for agent selection")
        if not capability_id.strip():
            raise AgentSelectionError("capability_id is required for agent selection")
        if not version.strip():
            raise AgentSelectionError("version is required for agent selection")

        try:
            return self.agent_registry.get(capability_id, version)
        except CapabilityNotFoundError as exc:
            raise AgentSelectionError(
                f"No agent registered for {capability_id}@{version}"
            ) from exc

    def execute(
        self,
        plan: Any = None,
        context: Any = None,
        *,
        objective: Optional[str] = None,
        capability_id: Optional[str] = None,
        version: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        invocation_id: Optional[str] = None,
    ) -> Any:
        """Execute either a plan or a single capability invocation."""
        if plan is not None:
            if self.orchestrator is None:
                raise SupervisorError("orchestrator is required for plan execution")
            if context is None:
                raise SupervisorError("context is required for plan execution")
            return self.orchestrator.execute(plan, context)

        if self.runtime is None:
            raise SupervisorError("runtime is required for direct execution")

        objective = objective or ""
        capability_id = capability_id or ""
        version = version or ""
        input_data = input_data or {}
        invocation_id = invocation_id or ""

        if not objective.strip():
            return InvocationResult(
                invocation_id=invocation_id,
                capability_id=capability_id,
                status=InvocationStatus.FAILED,
                output=None,
                error={
                    "type": "SupervisorValidationError",
                    "message": "objective is required",
                    "failure_class": "validation",
                    "recovery_action": "stop",
                },
            )

        if not capability_id.strip():
            return InvocationResult(
                invocation_id=invocation_id,
                capability_id=capability_id,
                status=InvocationStatus.FAILED,
                output=None,
                error={
                    "type": "SupervisorValidationError",
                    "message": "capability_id is required",
                    "failure_class": "validation",
                    "recovery_action": "stop",
                },
            )

        return self.runtime.execute(
            context=context,
            capability_id=capability_id,
            version=version,
            input_data=input_data,
            invocation_id=invocation_id,
        )

    def inspect(self, context: Any) -> SupervisionDecision:
        """Inspect the latest failure and produce a bounded recovery decision."""
        failure = getattr(context, "last_failure", None)
        if failure is None:
            return SupervisionDecision(
                action="continue",
                reason="No failure is recorded.",
                terminal=False,
            )

        decision: RecoveryDecision = self.recovery_policy.classify(
            failure,
            context,
        )
        return SupervisionDecision(
            action=decision.action,
            reason=decision.reason,
            terminal=decision.terminal,
        )

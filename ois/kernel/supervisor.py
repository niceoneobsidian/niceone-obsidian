from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ois.observability_telemetry import SupervisorExecutionTracker

from .contracts import InvocationRequest, InvocationResult, InvocationStatus
from .evidence import EvidenceLedger
from .policy import DefaultPolicyEngine, PolicyEngine
from .recovery import RecoveryDecision, RecoveryPolicy
from .registry import AgentRegistry, AgentRoutingError
from .state import ExecutionContext, ExecutionIdentity


class SupervisorError(Exception):
    """Base supervisor error."""


class AgentSelectionError(SupervisorError):
    """Raised when an execution cannot be delegated to an agent."""


@dataclass(frozen=True)
class SupervisorRequest:
    objective: str
    capability_id: str
    version: str
    input_data: dict[str, Any]
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
        agent_registry: AgentRegistry | None = None,
        orchestrator: Any = None,
        recovery_policy: RecoveryPolicy | None = None,
        policy: PolicyEngine | None = None,
        evidence: EvidenceLedger | None = None,
        availability: Any = None,
        telemetry: SupervisorExecutionTracker | None = None,
    ) -> None:
        self.runtime = runtime
        self.agent_registry = agent_registry
        self.orchestrator = orchestrator
        self.recovery_policy = recovery_policy or RecoveryPolicy()
        self.policy = policy or DefaultPolicyEngine()
        self.evidence = evidence
        self.availability = availability
        self.telemetry = telemetry

    def select_agent(
        self,
        capability_id: str,
        version: str,
        *,
        context: Any = None,
        input_data: dict[str, Any] | None = None,
        invocation_id: str = "agent-selection",
    ) -> Any:
        """Resolve exactly one authorized, available agent through AgentRegistry."""
        if self.agent_registry is None:
            raise AgentSelectionError("agent_registry is required for agent selection")
        if not capability_id.strip():
            raise AgentSelectionError("capability_id is required for agent selection")
        if not version.strip():
            raise AgentSelectionError("version is required for agent selection")

        selection_context = context or ExecutionContext(
            identity=ExecutionIdentity(),
            objective=f"Agent selection for {capability_id}@{version}",
        )
        request = InvocationRequest(
            invocation_id=invocation_id,
            capability_id=capability_id,
            input=input_data or {},
            execution=selection_context,
        )

        try:
            decision = self.agent_registry.route(
                capability_id,
                version,
                request=request,
                policy=self.policy,
                availability=self.availability,
            )
        except AgentRoutingError as exc:
            self._record_selection_evidence(
                selection_context,
                "agent.selection.rejected",
                capability_id,
                version,
                {"reason": str(exc)},
            )
            raise AgentSelectionError(str(exc)) from exc

        self._record_selection_evidence(
            selection_context,
            "agent.selection.selected",
            capability_id,
            version,
            {"reason": decision.reason},
        )
        return decision.selected

    def _record_selection_evidence(
        self,
        context: Any,
        event_type: str,
        capability_id: str,
        version: str,
        data: dict[str, Any],
    ) -> None:
        if self.evidence is not None:
            self.evidence.record(
                context.identity.execution_id,
                event_type,
                {
                    "capability_id": capability_id,
                    "version": version,
                    **data,
                },
            )

    def execute(
        self,
        plan: Any = None,
        context: Any = None,
        *,
        objective: str | None = None,
        capability_id: str | None = None,
        version: str | None = None,
        input_data: dict[str, Any] | None = None,
        invocation_id: str | None = None,
    ) -> Any:
        """Execute either a plan or a single capability invocation."""
        if plan is not None:
            if self.orchestrator is None:
                raise SupervisorError("orchestrator is required for plan execution")
            if context is None:
                raise SupervisorError("context is required for plan execution")
            return self._execute_plan(plan, context)

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

        return self._execute_direct(
            context=context,
            capability_id=capability_id,
            version=version,
            input_data=input_data,
            invocation_id=invocation_id,
        )

    def _execute_plan(self, plan: Any, context: ExecutionContext) -> Any:
        workflow_id = context.identity.workflow_id or "unknown"
        if self.telemetry is None:
            return self.orchestrator.execute(plan, context)
        with self.telemetry.track_execution(
            context.identity.tenant_id,
            str(context.identity.execution_id),
            workflow_id,
        ):
            return self.orchestrator.execute(plan, context)

    def _execute_direct(
        self,
        *,
        context: Any,
        capability_id: str,
        version: str,
        input_data: dict[str, Any],
        invocation_id: str,
    ) -> Any:
        if self.telemetry is None or context is None:
            return self.runtime.execute(
                context=context,
                capability_id=capability_id,
                version=version,
                input_data=input_data,
                invocation_id=invocation_id,
            )

        workflow_id = getattr(context.identity, "workflow_id", None) or capability_id
        with self.telemetry.track_execution(
            context.identity.tenant_id,
            str(context.identity.execution_id),
            workflow_id,
        ):
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

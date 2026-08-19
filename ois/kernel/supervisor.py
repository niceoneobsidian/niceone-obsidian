from __future__ import annotations

from dataclasses import dataclass

from .orchestrator import PlanOrchestrator
from .planning import ExecutionPlan
from .registry import AgentRegistry, CapabilityNotFoundError
from .state import ExecutionContext
from .types import ExecutionStatus


class SupervisorError(Exception):
    """Base supervisor error."""


class AgentSelectionError(SupervisorError):
    """Raised when the supervisor cannot select an agent."""


@dataclass(frozen=True)
class SupervisionDecision:
    action: str
    agent_id: str | None
    reason: str


class Supervisor:
    """
    Deterministic kernel-level supervision boundary.

    The Supervisor coordinates agent selection and plan execution.
    It does not directly invoke capabilities.

    Runtime remains responsible for individual capability execution.
    PlanOrchestrator remains responsible for plan-level execution.
    """

    def __init__(
        self,
        agent_registry: AgentRegistry,
        orchestrator: PlanOrchestrator,
    ) -> None:
        self.agent_registry = agent_registry
        self.orchestrator = orchestrator

    def select_agent(
        self,
        agent_id: str,
        version: str,
    ):
        """
        Resolve an agent through the AgentRegistry.

        Selection never bypasses the registry.
        """
        try:
            return self.agent_registry.get(
                agent_id,
                version,
            )
        except CapabilityNotFoundError as exc:
            raise AgentSelectionError(
                f"Agent not found: {agent_id}@{version}"
            ) from exc

    def inspect(
        self,
        context: ExecutionContext,
    ) -> SupervisionDecision:
        """
        Determine the next supervision action from execution state.
        """
        if context.status == ExecutionStatus.COMPLETED:
            return SupervisionDecision(
                action="complete",
                agent_id=None,
                reason="Execution is already complete.",
            )

        if context.status == ExecutionStatus.STOPPED:
            return SupervisionDecision(
                action="stop",
                agent_id=None,
                reason="Execution is terminally stopped.",
            )

        if context.last_failure is not None:
            return SupervisionDecision(
                action="recover",
                agent_id=None,
                reason="Execution contains a recorded failure.",
            )

        return SupervisionDecision(
            action="execute",
            agent_id=None,
            reason="Execution may proceed.",
        )

    def execute(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext,
    ) -> ExecutionPlan:
        """
        Execute a validated supervision plan through the orchestrator.

        The Supervisor never invokes an agent directly.
        """
        decision = self.inspect(context)

        if decision.action == "complete":
            return plan

        if decision.action == "stop":
            return plan

        return self.orchestrator.execute(
            plan,
            context,
        )

    def available_agents(self) -> tuple[object, ...]:
        """
        Return registered agent implementations.

        Discovery remains registry-backed.
        """
        return tuple(
            entry.capability
            for entry in self.agent_registry.list()
        )

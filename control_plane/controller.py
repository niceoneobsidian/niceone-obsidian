"""Authoritative OIS Control Plane coordinator."""

from __future__ import annotations

from collections.abc import Mapping

from ois.kernel.registry import CapabilityRegistry
from ois.registries import (
    AgentRegistry,
    ModelRegistry,
    ToolRegistry,
    WorkflowRegistry,
)

from .request import ControlRequest


class ControlPlane:
    """Coordinate registry resolution before authoritative Kernel execution.

    Capability execution uses the canonical Kernel registry. Agent, tool, model
    and workflow registries remain independently versioned Control Plane
    concerns. No parallel production execution path is introduced here.
    """

    def __init__(
        self,
        *,
        capabilities: CapabilityRegistry | None = None,
        agents: AgentRegistry | None = None,
        tools: ToolRegistry | None = None,
        models: ModelRegistry | None = None,
        workflows: WorkflowRegistry | None = None,
    ) -> None:
        self.capabilities = capabilities or CapabilityRegistry()
        self.agents = agents or AgentRegistry()
        self.tools = tools or ToolRegistry()
        self.models = models or ModelRegistry()
        self.workflows = workflows or WorkflowRegistry()

    def resolve_capability(self, request: ControlRequest) -> object:
        """Resolve a capability from the canonical Kernel registry."""
        entry = self.capabilities.get(request.capability_id, request.capability_version)
        if not callable(getattr(entry.capability, "invoke", None)):
            raise TypeError(
                f"registered capability is not executable: "
                f"{request.capability_id}@{request.capability_version}"
            )
        return entry.capability

    def snapshot(self) -> Mapping[str, tuple[object, ...]]:
        """Return deterministic registry snapshots for audit/inspection."""
        return {
            "capabilities": self.capabilities.list(),
            "agents": self.agents.snapshot(),
            "tools": self.tools.snapshot(),
            "models": self.models.snapshot(),
            "workflows": self.workflows.snapshot(),
        }

"""Authoritative control-plane coordinator."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from ois.registries import (
    AgentRegistry,
    CapabilityRegistry,
    ModelRegistry,
    ToolRegistry,
    WorkflowRegistry,
)

from .request import ControlRequest


class ControlPlane:
    """Resolve a registered capability before execution.

    The control plane is deliberately small: authorization, policy, routing,
    validation, and kernel execution remain explicit integration points rather
    than being silently duplicated here.
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

    def resolve_capability(self, request: ControlRequest) -> Callable[..., object]:
        entry = self.capabilities.resolve(
            request.capability_id,
            request.capability_version,
        )
        if not callable(entry.value):
            raise TypeError(
                f"registered capability is not callable: "
                f"{request.capability_id}@{request.capability_version}"
            )
        return entry.value

    def snapshot(self) -> Mapping[str, tuple[object, ...]]:
        """Return a deterministic registry snapshot for audit/inspection."""
        return {
            "capabilities": self.capabilities.snapshot(),
            "agents": self.agents.snapshot(),
            "tools": self.tools.snapshot(),
            "models": self.models.snapshot(),
            "workflows": self.workflows.snapshot(),
        }

"""Deterministic routing without execution."""

from __future__ import annotations

from ois.registries import (
    AgentRegistry,
    CapabilityRegistry,
    ModelRegistry,
    ToolRegistry,
)

from .spec import RouteRequest, RouteResult


class Router:
    """Resolve registered objects; never execute them."""

    def __init__(
        self,
        *,
        capabilities: CapabilityRegistry | None = None,
        agents: AgentRegistry | None = None,
        models: ModelRegistry | None = None,
        tools: ToolRegistry | None = None,
    ) -> None:
        self.capabilities = capabilities or CapabilityRegistry()
        self.agents = agents or AgentRegistry()
        self.models = models or ModelRegistry()
        self.tools = tools or ToolRegistry()

    def resolve_capability(self, request: RouteRequest) -> RouteResult:
        return self._resolve(self.capabilities, request)

    def resolve_agent(self, request: RouteRequest) -> RouteResult:
        return self._resolve(self.agents, request)

    def resolve_model(self, request: RouteRequest) -> RouteResult:
        return self._resolve(self.models, request)

    def resolve_tool(self, request: RouteRequest) -> RouteResult:
        return self._resolve(self.tools, request)

    @staticmethod
    def _resolve(
        registry: CapabilityRegistry | AgentRegistry | ModelRegistry | ToolRegistry,
        request: RouteRequest,
    ) -> RouteResult:
        entry = registry.resolve(request.object_id, request.version)
        contract = getattr(entry, "contract", None)
        if contract is not None:
            object_id = str(getattr(contract, "capability_id"))
            version = str(getattr(contract, "version"))
            value = getattr(entry, "capability")
        else:
            object_id = entry.id
            version = entry.version
            value = entry.value
        return RouteResult(
            object_id=object_id,
            version=version,
            value=value,
        )

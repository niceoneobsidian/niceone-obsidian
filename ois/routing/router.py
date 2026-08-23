"""Deterministic routing without execution."""

from __future__ import annotations

from typing import Protocol, TypeVar

from ois.registries import (
    AgentRegistry,
    CapabilityRegistry,
    ModelRegistry,
    ToolRegistry,
)

from .spec import RouteRequest, RouteResult


class _Registry(Protocol):
    def resolve(self, object_id: str, version: str) -> object: ...


RegistryT = TypeVar("RegistryT", bound=_Registry)


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
    def _resolve(registry: RegistryT, request: RouteRequest) -> RouteResult:
        entry = registry.resolve(request.object_id, request.version)
        return RouteResult(
            object_id=entry.id,
            version=entry.version,
            value=entry.value,
        )

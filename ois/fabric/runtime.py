"""Canonical Agent/Tool/Model fabric assembled from the existing OIS registries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ois.registries import AgentRegistry, ModelRegistry, ToolRegistry


class AgentProvider(Protocol):
    agent_id: str

    def invoke(self, objective: str, context: dict[str, Any]) -> Any: ...


class ToolProvider(Protocol):
    tool_id: str

    def invoke(self, arguments: dict[str, Any]) -> Any: ...


class ModelProvider(Protocol):
    model_id: str

    def invoke(self, prompt: str, options: dict[str, Any] | None = None) -> Any: ...


@dataclass(frozen=True)
class FabricSelection:
    agent_id: str
    agent_version: str
    model_id: str | None = None
    model_version: str | None = None
    tool_id: str | None = None
    tool_version: str | None = None


class OISFabric:
    """Registry-backed fabric; selection is deterministic and execution is explicit."""

    def __init__(self) -> None:
        self.agents = AgentRegistry()
        self.tools = ToolRegistry()
        self.models = ModelRegistry()

    def register_agent(self, agent_id: str, version: str, provider: AgentProvider) -> None:
        self.agents.register(agent_id, version, provider)

    def register_tool(self, tool_id: str, version: str, provider: ToolProvider) -> None:
        self.tools.register(tool_id, version, provider)

    def register_model(self, model_id: str, version: str, provider: ModelProvider) -> None:
        self.models.register(model_id, version, provider)

    def select_agent(self, agent_id: str, version: str) -> FabricSelection:
        self.agents.resolve(agent_id, version)
        return FabricSelection(agent_id=agent_id, agent_version=version)

    def invoke_tool(self, tool_id: str, version: str, arguments: dict[str, Any]) -> Any:
        provider = self.tools.resolve(tool_id, version).value
        invoke = getattr(provider, "invoke", None)
        if not callable(invoke):
            raise TypeError(f"registered tool is not executable: {tool_id}@{version}")
        return invoke(arguments)

    def invoke_model(self, model_id: str, version: str, prompt: str, options: dict[str, Any] | None = None) -> Any:
        provider = self.models.resolve(model_id, version).value
        invoke = getattr(provider, "invoke", None)
        if not callable(invoke):
            raise TypeError(f"registered model is not executable: {model_id}@{version}")
        return invoke(prompt, options)

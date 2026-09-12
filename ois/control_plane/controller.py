"""Authoritative control-plane coordinator."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

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
        # Registries in this codebase expose two different lookup APIs:
        # ois.kernel.registry.CapabilityRegistry.get() -> RegistryEntry(capability=...)
        # ois.registries.base.Registry.resolve() -> RegistryEntry(value=...)
        # Support both rather than assuming the kernel-style API.
        lookup = getattr(self.capabilities, "get", None)
        if not callable(lookup):
            lookup = getattr(self.capabilities, "resolve", None)
        if not callable(lookup):
            raise TypeError("capability registry does not provide a callable get/resolve")

        entry = lookup(request.capability_id, request.capability_version)

        candidate = getattr(entry, "capability", None)
        if candidate is None:
            candidate = getattr(entry, "value", None)

        if callable(candidate):
            return cast(Callable[..., object], candidate)

        # Capabilities implement the Kernel Capability protocol (`invoke`),
        # not necessarily a bare `execute` method.
        invoke = getattr(candidate, "invoke", None)
        if callable(invoke):
            return cast(Callable[..., object], invoke)

        execute = getattr(candidate, "execute", None)
        if callable(execute):
            return cast(Callable[..., object], execute)

        raise TypeError(
            f"registered capability is not callable: "
            f"{request.capability_id}@{request.capability_version}"
        )

    def execute(
        self,
        request: ControlRequest,
        *args: object,
        **kwargs: object,
    ) -> object:
        """Resolve and invoke the capability described by ``request``."""
        capability = self.resolve_capability(request)
        return capability(*args, **kwargs)

    def snapshot(self) -> Mapping[str, tuple[object, ...]]:
        """Return a deterministic registry snapshot for audit/inspection."""
        return {
            "capabilities": self.capabilities.snapshot(),
            "agents": self.agents.snapshot(),
            "tools": self.tools.snapshot(),
            "models": self.models.snapshot(),
            "workflows": self.workflows.snapshot(),
        }

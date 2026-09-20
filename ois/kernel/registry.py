"""Compatibility facade for the canonical OIS registry implementation."""

from ois.registries.core import (
    AgentRegistry,
    AgentRoutingDecision,
    AgentRoutingError,
    AgentUnavailableError,
    AmbiguousAgentError,
    CapabilityEntry,
    CapabilityNotFoundError,
    RegistryEntry,
    CapabilityRegistry,
    DuplicateCapabilityError,
    ModelRegistry,
    RegistryError,
    ToolRegistry,
    WorkflowRegistry,
)

__all__ = [
    "AgentRegistry",
    "AgentRoutingDecision",
    "AgentRoutingError",
    "AgentUnavailableError",
    "AmbiguousAgentError",
    "CapabilityEntry",
    "CapabilityNotFoundError",
    "RegistryEntry",
    "CapabilityRegistry",
    "DuplicateCapabilityError",
    "ModelRegistry",
    "RegistryError",
    "ToolRegistry",
    "WorkflowRegistry",
]

# Compatibility alias retained for Control Plane lifecycle adapters.
RegistryEntry = CapabilityEntry

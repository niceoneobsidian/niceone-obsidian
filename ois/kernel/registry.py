"""Compatibility facade for the canonical OIS registry implementation."""

from ois.registries.core import (
    AgentRegistry,
    AgentRoutingDecision,
    AgentRoutingError,
    AgentUnavailableError,
    AmbiguousAgentError,
    CapabilityEntry,
    CapabilityNotFoundError,
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
    "CapabilityRegistry",
    "DuplicateCapabilityError",
    "ModelRegistry",
    "RegistryError",
    "ToolRegistry",
    "WorkflowRegistry",
]

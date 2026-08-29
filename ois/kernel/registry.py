"""Compatibility exports for the canonical OIS registry boundary.

Registry implementations live exclusively in :mod:`ois.registries`.
"""

from ois.registries import (
    AgentRegistry,
    AgentRoutingDecision,
    AgentRoutingError,
    AgentUnavailableError,
    AmbiguousAgentError,
    CapabilityNotFoundError,
    CapabilityRegistry,
    CapabilityRegistryEntry,
    DuplicateCapabilityError,
    Registry,
    RegistryEntry,
    RegistryError,
    ToolRegistry,
)

__all__ = [
    "AgentRegistry",
    "AgentRoutingDecision",
    "AgentRoutingError",
    "AgentUnavailableError",
    "AmbiguousAgentError",
    "CapabilityNotFoundError",
    "CapabilityRegistry",
    "CapabilityRegistryEntry",
    "DuplicateCapabilityError",
    "Registry",
    "RegistryEntry",
    "RegistryError",
    "ToolRegistry",
]

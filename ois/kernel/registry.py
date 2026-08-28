"""Compatibility exports for the canonical registry boundary.

Registry implementations live in :mod:`ois.registries`. This module remains
only so existing Kernel imports continue to resolve during the migration.
"""

from ois.registries.capability_registry import (
    AgentRegistry,
    AgentRoutingDecision,
    AgentRoutingError,
    AgentUnavailableError,
    AmbiguousAgentError,
    CapabilityNotFoundError,
    CapabilityRegistry,
    DuplicateCapabilityError,
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
    "DuplicateCapabilityError",
    "RegistryError",
    "ToolRegistry",
]

"""Canonical OIS registry boundary."""

from .agent_registry import (
    AgentRegistry,
    AgentRoutingDecision,
    AgentRoutingError,
    AgentUnavailableError,
    AmbiguousAgentError,
)
from .base import Registry, RegistryEntry
from .capability_registry import (
    CapabilityNotFoundError,
    CapabilityRegistry,
    CapabilityRegistryEntry,
    DuplicateCapabilityError,
    RegistryError,
)
from .model_registry import ModelRegistry
from .tool_registry import ToolRegistry
from .workflow_registry import WorkflowRegistry

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
    "ModelRegistry",
    "Registry",
    "RegistryEntry",
    "RegistryError",
    "ToolRegistry",
    "WorkflowRegistry",
]

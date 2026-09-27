"""First-class OIS registries backed by one canonical implementation."""

from .agent_registry import AgentRegistry
from .base import Registry, RegistryEntry
from .capability_registry import CapabilityEntry, CapabilityRegistry
from .model_registry import ModelRegistry
from .tool_registry import ToolRegistry
from .workflow_registry import WorkflowRegistry

__all__ = [
    "AgentRegistry",
    "CapabilityEntry",
    "CapabilityRegistry",
    "ModelRegistry",
    "Registry",
    "RegistryEntry",
    "ToolRegistry",
    "WorkflowRegistry",
]

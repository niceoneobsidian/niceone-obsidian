"""First-class OIS registries."""

from .base import Registry, RegistryEntry
from .capability_registry import CapabilityRegistry
from .agent_registry import AgentRegistry
from .tool_registry import ToolRegistry
from .model_registry import ModelRegistry
from .workflow_registry import WorkflowRegistry

__all__ = [
    "AgentRegistry",
    "CapabilityRegistry",
    "ModelRegistry",
    "Registry",
    "RegistryEntry",
    "ToolRegistry",
    "WorkflowRegistry",
]

"""Workflow registry."""

from .base import Registry


class WorkflowRegistry(Registry[object]):
    """Registry for versioned workflows."""

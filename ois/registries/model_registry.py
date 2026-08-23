"""Model registry."""
from .base import Registry


class ModelRegistry(Registry[object]):
    """Registry for model providers and versions."""

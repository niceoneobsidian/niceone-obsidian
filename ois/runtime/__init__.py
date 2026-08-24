"""OIS runtime bindings for the structural fabric layer."""

from .fabrics import FabricRuntime, register_fabric_capabilities

__all__ = ["FabricRuntime", "register_fabric_capabilities"]

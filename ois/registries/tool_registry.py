"""Canonical tool registry."""

from ois.kernel.contracts import ToolContract

from .capability_registry import CapabilityRegistry, RegistryError


class ToolRegistry(CapabilityRegistry):
    """Registry specialized for governed tools."""

    def register(self, capability_or_id, version=None, value=None, *, metadata=None):
        registered = value if isinstance(capability_or_id, str) else capability_or_id
        contract = getattr(registered, "contract", None)
        if not isinstance(contract, ToolContract):
            raise RegistryError("ToolRegistry requires a ToolContract.")
        return super().register(
            capability_or_id,
            version,
            value,
            metadata=metadata,
        )

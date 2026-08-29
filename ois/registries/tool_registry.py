"""Canonical tool registry."""

from __future__ import annotations

from collections.abc import Mapping

from ois.kernel.contracts import Capability, ToolContract

from .capability_registry import CapabilityRegistry, CapabilityRegistryEntry, RegistryError


class ToolRegistry(CapabilityRegistry):
    """Registry specialized for governed tools."""

    def register(
        self,
        capability_or_id: Capability | str,
        version: str | None = None,
        value: object | None = None,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> CapabilityRegistryEntry:
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

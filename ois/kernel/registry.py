from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .contracts import AgentContract, Capability, CapabilityContract, ToolContract


class RegistryError(Exception):
    """Base registry error."""


class DuplicateCapabilityError(RegistryError):
    """Raised when a capability/version is registered twice."""


class CapabilityNotFoundError(RegistryError):
    """Raised when a requested capability cannot be found."""


@dataclass(frozen=True)
class RegistryEntry:
    capability: Capability
    contract: CapabilityContract


class CapabilityRegistry:
    """
    In-memory capability registry.

    The registry is intentionally infrastructure-light. Persistent discovery,
    service registration, health checks, and distributed coordination belong
    outside this foundational contract.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], RegistryEntry] = {}
        self._lock = RLock()

    def register(self, capability: Capability) -> None:
        contract = capability.contract
        key = (contract.capability_id, contract.version)

        with self._lock:
            if key in self._entries:
                raise DuplicateCapabilityError(
                    f"Capability already registered: "
                    f"{contract.capability_id}@{contract.version}"
                )

            self._entries[key] = RegistryEntry(
                capability=capability,
                contract=contract,
            )

    def unregister(self, capability_id: str, version: str) -> None:
        key = (capability_id, version)

        with self._lock:
            if key not in self._entries:
                raise CapabilityNotFoundError(
                    f"Capability not found: {capability_id}@{version}"
                )

            del self._entries[key]

    def get(self, capability_id: str, version: str) -> RegistryEntry:
        key = (capability_id, version)

        with self._lock:
            try:
                return self._entries[key]
            except KeyError as exc:
                raise CapabilityNotFoundError(
                    f"Capability not found: {capability_id}@{version}"
                ) from exc

    def list(self) -> tuple[RegistryEntry, ...]:
        with self._lock:
            return tuple(self._entries.values())

    def has(self, capability_id: str, version: str) -> bool:
        return (capability_id, version) in self._entries


class AgentRegistry(CapabilityRegistry):
    """Registry specialized for agent capabilities."""

    def register(self, capability: Capability) -> None:
        if not isinstance(capability.contract, AgentContract):
            raise RegistryError("AgentRegistry requires an AgentContract.")
        super().register(capability)


class ToolRegistry(CapabilityRegistry):
    """Registry specialized for tool capabilities."""

    def register(self, capability: Capability) -> None:
        if not isinstance(capability.contract, ToolContract):
            raise RegistryError("ToolRegistry requires a ToolContract.")
        super().register(capability)

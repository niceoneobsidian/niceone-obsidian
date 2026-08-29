"""Canonical capability registry."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import overload

from ois.kernel.contracts import Capability, CapabilityContract

from .base import Registry, RegistryEntry


class RegistryError(Exception):
    """Base capability-registry error."""


class DuplicateCapabilityError(RegistryError, ValueError):
    """Raised when a capability/version is registered twice."""


class CapabilityNotFoundError(RegistryError, KeyError):
    """Raised when a requested capability cannot be found."""


@dataclass(frozen=True)
class CapabilityRegistryEntry(RegistryEntry[object]):
    """Registry entry retaining the Kernel capability compatibility surface."""

    @property
    def capability(self) -> object:
        return self.value

    @property
    def contract(self) -> CapabilityContract:
        contract = getattr(self.value, "contract", None)
        if not isinstance(contract, CapabilityContract):
            raise TypeError(
                f"registered capability has no CapabilityContract: {self.id}@{self.version}"
            )
        return contract


class CapabilityRegistry(Registry[object]):
    """Canonical versioned registry for executable OIS capabilities."""

    def _make_entry(
        self,
        object_id: str,
        version: str,
        value: object,
        metadata: Mapping[str, object] | None,
    ) -> CapabilityRegistryEntry:
        return CapabilityRegistryEntry(
            id=object_id,
            version=version,
            value=value,
            metadata=dict(metadata or {}),
        )

    @overload
    def register(
        self,
        capability: Capability,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> CapabilityRegistryEntry: ...

    @overload
    def register(
        self,
        object_id: str,
        version: str,
        value: object,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> CapabilityRegistryEntry: ...

    def register(
        self,
        capability_or_id: Capability | str,
        version: str | None = None,
        value: object | None = None,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> CapabilityRegistryEntry:
        if isinstance(capability_or_id, str):
            if version is None:
                raise ValueError("registry version is required")
            try:
                return super().register(
                    capability_or_id,
                    version,
                    value,
                    metadata=metadata,
                )  # type: ignore[return-value]
            except ValueError as exc:
                if "already registered" in str(exc):
                    raise DuplicateCapabilityError(str(exc)) from exc
                raise

        capability = capability_or_id
        contract = getattr(capability, "contract", None)
        if not isinstance(contract, CapabilityContract):
            raise RegistryError("CapabilityRegistry requires a CapabilityContract.")
        try:
            return super().register(
                contract.capability_id,
                contract.version,
                capability,
                metadata=metadata,
            )  # type: ignore[return-value]
        except ValueError as exc:
            if "already registered" in str(exc):
                raise DuplicateCapabilityError(str(exc)) from exc
            raise

    def resolve(self, object_id: str, version: str) -> CapabilityRegistryEntry:
        try:
            return super().resolve(object_id, version)  # type: ignore[return-value]
        except KeyError as exc:
            raise CapabilityNotFoundError(
                f"Capability not found: {object_id}@{version}"
            ) from exc

    def get(self, object_id: str, version: str) -> CapabilityRegistryEntry:
        return self.resolve(object_id, version)

    def unregister(self, capability_id: str, version: str) -> None:
        key = (capability_id, version)
        with self._lock:
            if key not in self._entries:
                raise CapabilityNotFoundError(
                    f"Capability not found: {capability_id}@{version}"
                )
            del self._entries[key]

    def list(self) -> tuple[CapabilityRegistryEntry, ...]:
        return self.snapshot()

    def snapshot(self) -> tuple[CapabilityRegistryEntry, ...]:
        return super().snapshot()  # type: ignore[return-value]

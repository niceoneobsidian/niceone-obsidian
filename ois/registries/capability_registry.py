"""Capability registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import Registry, RegistryEntry


@dataclass(frozen=True)
class ResolvedCapabilityEntry:
    """Registry entry enriched with kernel-style capability/contract access.

    Returned by :meth:`CapabilityRegistry.get` when the registered value
    exposes a ``contract`` attribute (the Kernel Capability protocol), so
    that both styles of consumer see a consistent, correct object:
    ``entry.value`` (Registry Plane) and ``entry.capability`` /
    ``entry.contract`` (Kernel Plane).
    """

    value: Any
    capability: Any
    contract: Any


class CapabilityRegistry(Registry[object]):
    """Registry for executable OIS capabilities.

    Builds on :class:`~ois.registries.base.Registry` so both registration
    styles work:

    - Plain callables/values: ``register(id, version, value)`` and
      ``resolve(id, version).value``.
    - Kernel-style capabilities exposing a ``contract`` attribute:
      ``get(id, version)`` additionally exposes ``.capability`` and
      ``.contract`` so kernel execution code can use them directly.
    """

    def get(
        self, capability_id: str, version: str
    ) -> RegistryEntry[object] | ResolvedCapabilityEntry:
        entry = self.resolve(capability_id, version)
        contract = getattr(entry.value, "contract", None)
        if contract is None:
            return entry
        return ResolvedCapabilityEntry(
            value=entry.value,
            capability=entry.value,
            contract=contract,
        )

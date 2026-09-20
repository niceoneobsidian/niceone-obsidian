"""Capability registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import Registry, RegistryEntry


@dataclass(frozen=True)
class ResolvedCapabilityEntry:
    """Registry entry enriched with kernel-style capability/contract access."""

    value: Any
    capability: Any
    contract: Any


class CapabilityRegistry(Registry[object]):
    """Registry for executable OIS capabilities."""

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

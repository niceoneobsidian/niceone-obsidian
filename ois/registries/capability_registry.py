"""Canonical capability, agent, and tool registry implementations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any

from ois.kernel.contracts import AgentContract, Capability, ToolContract
from ois.kernel.policy import AuthorizationDenied, PolicyEngine

from .base import Registry, RegistryEntry


class RegistryError(Exception):
    """Base registry error."""


class DuplicateCapabilityError(RegistryError):
    """Raised when a capability/version is registered twice."""


class CapabilityNotFoundError(RegistryError):
    """Raised when a requested capability cannot be found."""


class AgentRoutingError(RegistryError):
    """Raised when an agent cannot be selected safely."""


class AgentUnavailableError(AgentRoutingError):
    """Raised when the registered agent is unavailable."""


class AmbiguousAgentError(AgentRoutingError):
    """Raised when routing produces more than one eligible agent."""


@dataclass(frozen=True)
class AgentRoutingDecision:
    capability_id: str
    version: str
    selected: RegistryEntry[Capability]
    candidates: tuple[RegistryEntry[Capability], ...]
    reason: str


class CapabilityRegistry(Registry[Capability]):
    """Canonical in-memory registry for versioned executable capabilities."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = RLock()

    def register(
        self,
        capability_or_id: Capability | str,
        version: str | None = None,
        value: Capability | None = None,
        *,
        metadata: dict[str, object] | None = None,
    ) -> RegistryEntry[Capability]:
        """Register either a contracted capability or a generic registry value.

        The object form is authoritative for executable capabilities. The
        three-argument form is retained for the generic control-plane contract
        tests and for non-executable registry compatibility.
        """
        if isinstance(capability_or_id, str):
            if version is None or value is None:
                raise TypeError("id, version, and value are required")
            object_id = capability_or_id
            capability = value
        else:
            if version is not None or value is not None:
                raise TypeError("capability registration accepts one object")
            capability = capability_or_id
            contract = capability.contract
            object_id = contract.capability_id
            version = contract.version

        key = (object_id, version)
        with self._lock:
            if key in self._entries:
                raise DuplicateCapabilityError(
                    f"Capability already registered: {object_id}@{version}"
                )
            return super().register(object_id, version, capability, metadata=metadata)

    def unregister(self, capability_id: str, version: str) -> None:
        key = (capability_id, version)
        with self._lock:
            if key not in self._entries:
                raise CapabilityNotFoundError(f"Capability not found: {capability_id}@{version}")
            del self._entries[key]

    def get(self, capability_id: str, version: str) -> RegistryEntry[Capability]:
        try:
            return self.resolve(capability_id, version)
        except KeyError as exc:
            raise CapabilityNotFoundError(
                f"Capability not found: {capability_id}@{version}"
            ) from exc

    def list(self) -> tuple[RegistryEntry[Capability], ...]:
        return self.snapshot()

    def has(self, capability_id: str, version: str) -> bool:
        return self.contains(capability_id, version)


class AgentRegistry(CapabilityRegistry):
    """Canonical registry specialized for governed agent routing."""

    def register(
        self,
        capability: Capability,
        version: str | None = None,
        value: Capability | None = None,
        *,
        metadata: dict[str, object] | None = None,
    ) -> RegistryEntry[Capability]:
        if version is not None or value is not None:
            raise TypeError("AgentRegistry requires a contracted agent object")
        if not isinstance(capability.contract, AgentContract):
            raise RegistryError("AgentRegistry requires an AgentContract.")
        return super().register(capability, metadata=metadata)

    def route(
        self,
        capability_id: str,
        version: str,
        *,
        request: Any,
        policy: PolicyEngine,
        availability: Callable[[RegistryEntry[Capability]], bool] | None = None,
    ) -> AgentRoutingDecision:
        """Select exactly one policy-authorized, available agent deterministically."""
        candidates = tuple(
            entry
            for entry in self.list()
            if entry.contract.capability_id == capability_id
            and entry.contract.version == version
            and isinstance(entry.contract, AgentContract)
        )
        if not candidates:
            raise AgentRoutingError(f"No agent registered for {capability_id}@{version}")

        eligible: list[RegistryEntry[Capability]] = []
        rejected: list[str] = []
        for entry in sorted(
            candidates,
            key=lambda item: (
                item.contract.capability_id,
                item.contract.version,
                type(item.capability).__module__,
                type(item.capability).__qualname__,
            ),
        ):
            try:
                policy.authorize(request, entry.contract)
            except AuthorizationDenied as exc:
                rejected.append(str(exc))
                continue
            if availability is not None and not availability(entry):
                rejected.append(
                    f"Agent unavailable: {entry.contract.capability_id}@{entry.contract.version}"
                )
                continue
            eligible.append(entry)

        if not eligible:
            reason = "; ".join(rejected) or "No eligible agent matched routing policy."
            raise AgentRoutingError(reason)
        if len(eligible) > 1:
            raise AmbiguousAgentError(
                f"Ambiguous agent routing for {capability_id}@{version}: "
                f"{len(eligible)} eligible agents"
            )
        return AgentRoutingDecision(
            capability_id=capability_id,
            version=version,
            selected=eligible[0],
            candidates=tuple(eligible),
            reason="Selected the sole eligible agent after policy and availability filtering.",
        )


class ToolRegistry(CapabilityRegistry):
    """Canonical registry specialized for tool capabilities."""

    def register(
        self,
        capability: Capability,
        version: str | None = None,
        value: Capability | None = None,
        *,
        metadata: dict[str, object] | None = None,
    ) -> RegistryEntry[Capability]:
        if version is not None or value is not None:
            raise TypeError("ToolRegistry requires a contracted tool object")
        if not isinstance(capability.contract, ToolContract):
            raise RegistryError("ToolRegistry requires a ToolContract.")
        return super().register(capability, metadata=metadata)

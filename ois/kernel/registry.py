from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any

from .contracts import AgentContract, Capability, CapabilityContract, ToolContract
from .policy import AuthorizationDenied, PolicyEngine


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
class RegistryEntry:
    capability: Capability
    contract: CapabilityContract


@dataclass(frozen=True)
class AgentRoutingDecision:
    capability_id: str
    version: str
    selected: RegistryEntry
    candidates: tuple[RegistryEntry, ...]
    reason: str


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
                raise DuplicateCapabilityError(f"Capability already registered: {contract.capability_id}@{contract.version}")

            self._entries[key] = RegistryEntry(
                capability=capability,
                contract=contract,
            )

    def unregister(self, capability_id: str, version: str) -> None:
        key = (capability_id, version)

        with self._lock:
            if key not in self._entries:
                raise CapabilityNotFoundError(f"Capability not found: {capability_id}@{version}")

            del self._entries[key]

    def get(self, capability_id: str, version: str) -> RegistryEntry:
        key = (capability_id, version)

        with self._lock:
            try:
                return self._entries[key]
            except KeyError as exc:
                raise CapabilityNotFoundError(f"Capability not found: {capability_id}@{version}") from exc

    def list(self) -> tuple[RegistryEntry, ...]:
        with self._lock:
            return tuple(self._entries.values())

    def resolve(self, capability_id: str, version: str) -> RegistryEntry:
        return self.get(capability_id, version)

    def has(self, capability_id: str, version: str) -> bool:
        return (capability_id, version) in self._entries


class AgentRegistry(CapabilityRegistry):
    """Registry specialized for governed agent routing."""

    def register(self, capability: Capability) -> None:
        if not isinstance(capability.contract, AgentContract):
            raise RegistryError("AgentRegistry requires an AgentContract.")
        super().register(capability)

    def route(
        self,
        capability_id: str,
        version: str,
        *,
        request: Any,
        policy: PolicyEngine,
        availability: Callable[[RegistryEntry], bool] | None = None,
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

        eligible: list[RegistryEntry] = []
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
                rejected.append(f"Agent unavailable: {entry.contract.capability_id}@{entry.contract.version}")
                continue

            eligible.append(entry)

        if not eligible:
            reason = "; ".join(rejected) or "No eligible agent matched routing policy."
            raise AgentRoutingError(reason)

        if len(eligible) > 1:
            raise AmbiguousAgentError(f"Ambiguous agent routing for {capability_id}@{version}: {len(eligible)} eligible agents")

        return AgentRoutingDecision(
            capability_id=capability_id,
            version=version,
            selected=eligible[0],
            candidates=tuple(eligible),
            reason="Selected the sole eligible agent after policy and availability filtering.",
        )


class ToolRegistry(CapabilityRegistry):
    """Registry specialized for tool capabilities."""

    def register(self, capability: Capability) -> None:
        if not isinstance(capability.contract, ToolContract):
            raise RegistryError("ToolRegistry requires a ToolContract.")
        super().register(capability)

"""Canonical OIS registry implementations.

This module is the single registry authority. Compatibility modules re-export these classes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RegistryEntry(Generic[T]):
    """Versioned generic registry entry."""

    id: str
    version: str
    value: T
    metadata: Mapping[str, object] = field(default_factory=dict)


class Registry(Generic[T]):
    """Deterministic versioned registry for non-executable registry planes."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], RegistryEntry[T]] = {}
        self._lock = RLock()

    def register(
        self,
        object_id: str,
        version: str,
        value: T,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> RegistryEntry[T]:
        if not object_id or not version:
            raise ValueError("registry id and version are required")
        key = (object_id, version)
        with self._lock:
            if key in self._entries:
                raise ValueError(f"already registered: {object_id}@{version}")
            entry = RegistryEntry(object_id, version, value, dict(metadata or {}))
            self._entries[key] = entry
            return entry

    def resolve(self, object_id: str, version: str) -> RegistryEntry[T]:
        with self._lock:
            try:
                return self._entries[(object_id, version)]
            except KeyError as exc:
                raise KeyError(f"not registered: {object_id}@{version}") from exc

    def get(self, object_id: str, version: str) -> RegistryEntry[T]:
        return self.resolve(object_id, version)

    def contains(self, object_id: str, version: str) -> bool:
        return (object_id, version) in self._entries

    def snapshot(self) -> tuple[RegistryEntry[T], ...]:
        with self._lock:
            return tuple(self._entries[key] for key in sorted(self._entries))


class RegistryError(Exception):
    """Base executable registry error."""


class DuplicateCapabilityError(RegistryError):
    """Raised when an executable capability/version is registered twice."""


class CapabilityNotFoundError(KeyError, RegistryError):
    """Raised when a requested executable capability cannot be found."""


class AgentRoutingError(RegistryError):
    """Raised when an agent cannot be selected safely."""


class AgentUnavailableError(AgentRoutingError):
    """Raised when a registered agent is unavailable."""


class AmbiguousAgentError(AgentRoutingError):
    """Raised when routing produces more than one eligible agent."""


@dataclass(frozen=True)
class CapabilityEntry:
    capability: Any
    contract: Any
    id: str
    version: str

    @property
    def value(self) -> Any:
        return self.capability


def _agent_contract_type() -> type[Any]:
    from ois.kernel.contracts import AgentContract

    return AgentContract


def _tool_contract_type() -> type[Any]:
    from ois.kernel.contracts import ToolContract

    return ToolContract


def _authorization_denied_type() -> type[Exception]:
    from ois.kernel.policy import AuthorizationDenied

    return AuthorizationDenied


class CapabilityRegistry:
    """Canonical capability registry with legacy and kernel-native registration forms."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], CapabilityEntry] = {}
        self._lock = RLock()

    def register(
        self,
        capability_or_id: Any,
        version: str | None = None,
        value: Any = None,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        if isinstance(capability_or_id, str):
            if not version:
                raise ValueError("registry id and version are required")
            capability_id = capability_or_id
            capability_version = version
            capability = value
        else:
            capability = capability_or_id
            contract = capability.contract
            capability_id = contract.capability_id
            capability_version = contract.version

        if capability is None:
            raise ValueError("registry value is required")

        contract = getattr(capability, "contract", None)
        key = (capability_id, capability_version)
        with self._lock:
            if key in self._entries:
                raise DuplicateCapabilityError(
                    f"Capability already registered: {capability_id}@{capability_version}"
                )
            self._entries[key] = CapabilityEntry(
                capability=capability,
                contract=contract,
                id=capability_id,
                version=capability_version,
            )

    def unregister(self, capability_id: str, version: str) -> None:
        with self._lock:
            if (capability_id, version) not in self._entries:
                raise CapabilityNotFoundError(f"not registered: {capability_id}@{version}")
            del self._entries[(capability_id, version)]

    def get(self, capability_id: str, version: str) -> CapabilityEntry:
        with self._lock:
            try:
                return self._entries[(capability_id, version)]
            except KeyError as exc:
                raise CapabilityNotFoundError(
                    f"not registered: {capability_id}@{version}"
                ) from exc

    def resolve(self, capability_id: str, version: str) -> CapabilityEntry:
        return self.get(capability_id, version)

    def has(self, capability_id: str, version: str) -> bool:
        return (capability_id, version) in self._entries

    def contains(self, capability_id: str, version: str) -> bool:
        return self.has(capability_id, version)

    def list(self) -> tuple[CapabilityEntry, ...]:
        with self._lock:
            return tuple(self._entries.values())

    def snapshot(self) -> tuple[CapabilityEntry, ...]:
        return self.list()


@dataclass(frozen=True)
class AgentRoutingDecision:
    capability_id: str
    version: str
    selected: CapabilityEntry
    candidates: tuple[CapabilityEntry, ...]
    reason: str


class AgentRegistry(CapabilityRegistry):
    """Canonical registry specialized for governed agent routing."""

    def register(
        self,
        capability_or_id: Any,
        version: str | None = None,
        value: Any = None,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        if not isinstance(capability_or_id, str):
            contract = getattr(capability_or_id, "contract", None)
            if not isinstance(contract, _agent_contract_type()):
                raise RegistryError("AgentRegistry requires an AgentContract.")
        super().register(
            capability_or_id,
            version,
            value,
            metadata=metadata,
        )

    def route(
        self,
        capability_id: str,
        version: str,
        *,
        request: Any,
        policy: Any,
        availability: Callable[[CapabilityEntry], bool] | None = None,
    ) -> AgentRoutingDecision:
        agent_contract = _agent_contract_type()
        candidates = tuple(
            entry
            for entry in self.list()
            if isinstance(entry.contract, agent_contract)
            and entry.contract.capability_id == capability_id
            and entry.contract.version == version
        )
        if not candidates:
            raise AgentRoutingError(
                f"No agent registered for {capability_id}@{version}"
            )

        eligible: list[CapabilityEntry] = []
        rejected: list[str] = []
        authorization_denied = _authorization_denied_type()

        for entry in candidates:
            try:
                policy.authorize(request, entry.contract)
            except authorization_denied as exc:
                rejected.append(str(exc))
                continue

            if availability is not None and not availability(entry):
                rejected.append(f"Agent unavailable: {capability_id}@{version}")
                continue
            eligible.append(entry)

        if not eligible:
            raise AgentRoutingError(
                "; ".join(rejected) or "No eligible agent matched routing policy."
            )

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
            reason=("Selected the sole eligible agent after policy and availability filtering."),
        )


class ToolRegistry(CapabilityRegistry):
    """Canonical registry specialized for governed tools."""

    def register(
        self,
        capability_or_id: Any,
        version: str | None = None,
        value: Any = None,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        if not isinstance(capability_or_id, str):
            contract = getattr(capability_or_id, "contract", None)
            if not isinstance(contract, _tool_contract_type()):
                raise RegistryError("ToolRegistry requires a ToolContract.")
        super().register(
            capability_or_id,
            version,
            value,
            metadata=metadata,
        )


class ModelRegistry(Registry[Any]):
    """Canonical registry for model providers and versions."""


class WorkflowRegistry(Registry[Any]):
    """Canonical registry for versioned workflows."""

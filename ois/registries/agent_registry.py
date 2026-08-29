"""Canonical agent registry."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from ois.kernel.contracts import AgentContract, Capability
from ois.kernel.policy import AuthorizationDenied, PolicyEngine

from .capability_registry import CapabilityRegistry, CapabilityRegistryEntry, RegistryError


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
    selected: CapabilityRegistryEntry
    candidates: tuple[CapabilityRegistryEntry, ...]
    reason: str


class AgentRegistry(CapabilityRegistry):
    """Registry specialized for governed agent routing."""

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
        if not isinstance(contract, AgentContract):
            raise RegistryError("AgentRegistry requires an AgentContract.")
        return super().register(
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
        policy: PolicyEngine,
        availability: Callable[[CapabilityRegistryEntry], bool] | None = None,
    ) -> AgentRoutingDecision:
        """Select exactly one policy-authorized, available agent deterministically."""
        candidates = tuple(
            entry
            for entry in self.list()
            if entry.id == capability_id
            and entry.version == version
            and isinstance(entry.contract, AgentContract)
        )
        if not candidates:
            raise AgentRoutingError(f"No agent registered for {capability_id}@{version}")

        eligible: list[CapabilityRegistryEntry] = []
        rejected: list[str] = []
        for entry in candidates:
            try:
                policy.authorize(request, entry.contract)
            except AuthorizationDenied as exc:
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
            reason="Selected the sole eligible agent after policy and availability filtering.",
        )

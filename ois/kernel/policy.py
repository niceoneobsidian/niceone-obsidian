from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .contracts import (
    CapabilityContract,
    InvocationRequest,
)
from .types import RiskLevel, SideEffectLevel


class PolicyError(Exception):
    """Base policy error."""


class AuthorizationDenied(PolicyError):
    """Raised when a capability invocation is not authorized."""


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()
    requires_approval: bool = False


class DefaultPolicyEngine:
    """
    Conservative foundational policy engine.

    Default behavior is deny-by-default for explicitly restricted conditions.
    More sophisticated RBAC/ABAC and tenant policy can be layered above this
    interface later.
    """

    def __init__(
        self,
        allowed_permissions: Iterable[str] = (),
        maximum_risk: RiskLevel = RiskLevel.MEDIUM,
        allow_irreversible: bool = False,
    ) -> None:
        self._allowed_permissions = frozenset(allowed_permissions)
        self._maximum_risk = maximum_risk
        self._allow_irreversible = allow_irreversible

    def authorize(
        self,
        request: InvocationRequest,
        contract: CapabilityContract,
    ) -> bool:
        decision = self.evaluate(request, contract)

        if not decision.allowed:
            raise AuthorizationDenied("; ".join(decision.reasons))

        return True

    def evaluate(
        self,
        request: InvocationRequest,
        contract: CapabilityContract,
    ) -> PolicyDecision:
        reasons: list[str] = []

        if not request.execution.identity.tenant_id:
            reasons.append("Execution must have a tenant identity.")

        risk_order = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }

        if risk_order[contract.risk_level] > risk_order[self._maximum_risk]:
            reasons.append(
                f"Capability risk exceeds policy limit: {contract.risk_level.value}"
            )

        required_permissions = set(contract.permissions)
        missing_permissions = required_permissions - self._allowed_permissions

        if missing_permissions:
            reasons.append(
                "Missing permissions: "
                + ", ".join(sorted(missing_permissions))
            )

        if (
            contract.side_effects == SideEffectLevel.IRREVERSIBLE
            and not self._allow_irreversible
        ):
            reasons.append("Irreversible side effects are not permitted.")

        requires_approval = (
            contract.risk_level in {
                RiskLevel.HIGH,
                RiskLevel.CRITICAL,
            }
            or contract.side_effects == SideEffectLevel.IRREVERSIBLE
        )

        return PolicyDecision(
            allowed=not reasons,
            reasons=tuple(reasons),
            requires_approval=requires_approval,
        )

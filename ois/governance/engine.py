from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from json import dumps
from uuid import uuid4

from .models import AuditEvent, DecisionProvenance
from .stores import InMemoryGovernanceStore


@dataclass(frozen=True)
class GovernanceDecision:
    allowed: bool
    reason: str
    decision_id: str


class GovernanceEngine:
    """Fail-closed governance boundary for autonomous actions."""

    def __init__(self, store: InMemoryGovernanceStore | None = None) -> None:
        self.store = store or InMemoryGovernanceStore()

    def authorize(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        execution_id: str,
        agent_id: str,
        action: str,
        capability_id: str,
        inputs: dict,
        estimated_cost: float = 0.0,
    ) -> GovernanceDecision:
        decision_id = str(uuid4())
        identity = self.store.agents.get((tenant_id, agent_id))
        reason = "authorized"
        allowed = True
        if identity is None or not identity.enabled:
            allowed, reason = False, "agent identity is not active"
        else:
            grant = self.store.grants.get((tenant_id, agent_id, capability_id))
            if grant is None or not grant.active():
                allowed, reason = False, "capability grant is missing or expired"
            elif grant.allowed_actions and action not in grant.allowed_actions:
                allowed, reason = False, "action is not granted"
            else:
                limit = self.store.limits.get((tenant_id, action))
                if limit is not None:
                    count = self.store.action_counts[(tenant_id, action)]
                    if count >= limit.max_count:
                        allowed, reason = False, "autonomous action limit exceeded"
                if allowed and estimated_cost:
                    budgets = [b for (t, _), b in self.store.budgets.items() if t == tenant_id]
                    if not budgets or not any(b.can_spend(estimated_cost) for b in budgets):
                        allowed, reason = False, "action budget exceeded"

        digest = sha256(
            dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        provenance = DecisionProvenance(
            decision_id=decision_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            execution_id=execution_id,
            actor_id=agent_id,
            action=action,
            outcome="allow" if allowed else "deny",
            policy_id=None,
            policy_version=None,
            capability_id=capability_id,
            inputs_digest=digest,
            rationale=reason,
        )
        self.store.record_decision(provenance)
        self.store.record_audit(
            AuditEvent(
                event_id=str(uuid4()),
                tenant_id=tenant_id,
                actor_id=agent_id,
                action=action,
                resource=capability_id,
                outcome="allowed" if allowed else "denied",
                execution_id=execution_id,
                metadata={"decision_id": decision_id, "reason": reason},
            )
        )
        if allowed:
            self.store.count_action(tenant_id, action)
        return GovernanceDecision(allowed, reason, decision_id)

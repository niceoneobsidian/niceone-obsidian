from __future__ import annotations

import collections
from dataclasses import replace

from .models import (
    ActionBudget,
    ActionLimit,
    AgentIdentity,
    AuditEvent,
    CapabilityGrant,
    ComplianceEvidence,
    DecisionProvenance,
    PolicyVersion,
    SLO,
)


class InMemoryGovernanceStore:
    """Deterministic reference store; production storage is PostgreSQL-backed."""

    def __init__(self) -> None:
        self.agents: dict[tuple[str, str], AgentIdentity] = {}
        self.grants: dict[tuple[str, str, str], CapabilityGrant] = {}
        self.policies: dict[tuple[str, str, str], PolicyVersion] = {}
        self.decisions: list[DecisionProvenance] = []
        self.audit: list[AuditEvent] = []
        self.evidence: list[ComplianceEvidence] = []
        self.budgets: dict[tuple[str, str], ActionBudget] = {}
        self.limits: dict[tuple[str, str], ActionLimit] = {}
        self.action_counts: collections.defaultdict[tuple[str, str], int] = collections.defaultdict(int)
        self.slos: dict[tuple[str, str], SLO] = {}

    def put_agent(self, identity: AgentIdentity) -> None:
        if not identity.tenant_id:
            raise ValueError("tenant_id is required")
        self.agents[(identity.tenant_id, identity.agent_id)] = identity

    def grant(self, grant: CapabilityGrant) -> None:
        self.grants[(grant.tenant_id, grant.agent_id, grant.capability_id)] = grant

    def put_policy(self, policy: PolicyVersion) -> None:
        self.policies[(policy.tenant_id, policy.policy_id, policy.version)] = policy

    def put_budget(self, budget: ActionBudget) -> None:
        if budget.max_cost < 0:
            raise ValueError("max_cost must be non-negative")
        self.budgets[(budget.tenant_id, budget.budget_id)] = budget

    def put_limit(self, limit: ActionLimit) -> None:
        if limit.max_count < 0:
            raise ValueError("max_count must be non-negative")
        self.limits[(limit.tenant_id, limit.action)] = limit

    def record_decision(self, decision: DecisionProvenance) -> None:
        self.decisions.append(decision)

    def record_audit(self, event: AuditEvent) -> None:
        self.audit.append(event)

    def record_evidence(self, evidence: ComplianceEvidence) -> None:
        self.evidence.append(evidence)

    def set_slo(self, slo: SLO) -> None:
        if not 0 <= slo.target <= 1:
            raise ValueError("SLO target must be between 0 and 1")
        self.slos[(slo.tenant_id, slo.name)] = slo

    def spend(self, tenant_id: str, budget_id: str, amount: float) -> None:
        key = (tenant_id, budget_id)
        budget = self.budgets.get(key)
        if budget is None:
            raise KeyError(f"budget not found: {budget_id}")
        if not budget.can_spend(amount):
            raise PermissionError("action budget exceeded")
        self.budgets[key] = replace(budget, spent_cost=budget.spent_cost + amount)

    def count_action(self, tenant_id: str, action: str) -> int:
        key = (tenant_id, action)
        self.action_counts[key] += 1
        return self.action_counts[key]

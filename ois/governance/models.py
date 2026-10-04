from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class AgentIdentity:
    agent_id: str
    tenant_id: str
    role: str
    trust_level: str = "standard"
    enabled: bool = True


@dataclass(frozen=True)
class CapabilityGrant:
    capability_id: str
    tenant_id: str
    agent_id: str
    allowed_actions: tuple[str, ...] = ()
    expires_at: datetime | None = None

    def active(self, now: datetime | None = None) -> bool:
        return self.expires_at is None or self.expires_at > (now or utc_now())


@dataclass(frozen=True)
class PolicyVersion:
    policy_id: str
    version: str
    tenant_id: str
    rules: Mapping[str, Any]
    content_hash: str
    active: bool = True


@dataclass(frozen=True)
class DecisionProvenance:
    decision_id: str
    tenant_id: str
    workspace_id: str
    execution_id: str
    actor_id: str
    action: str
    outcome: str
    policy_id: str | None
    policy_version: str | None
    capability_id: str | None
    inputs_digest: str
    rationale: str
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    tenant_id: str
    actor_id: str
    action: str
    resource: str
    outcome: str
    execution_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ActionBudget:
    tenant_id: str
    budget_id: str
    max_cost: float
    spent_cost: float = 0.0

    def can_spend(self, amount: float) -> bool:
        return amount >= 0 and self.spent_cost + amount <= self.max_cost


@dataclass(frozen=True)
class ActionLimit:
    tenant_id: str
    action: str
    max_count: int
    window_seconds: int = 3600


@dataclass(frozen=True)
class ComplianceEvidence:
    evidence_id: str
    tenant_id: str
    control_id: str
    subject: str
    evidence_type: str
    digest: str
    source: str
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class SLO:
    name: str
    tenant_id: str
    target: float
    metric: str
    window_seconds: int = 86400

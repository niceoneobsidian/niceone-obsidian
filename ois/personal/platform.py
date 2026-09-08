"""Governed personal-runtime composition root.

This layer integrates the existing OIS kernel/registries without replacing them.
It provides the stable application boundary needed by a personal control surface,
while keeping provider-specific implementations behind adapters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4


class ApprovalPolicy(StrEnum):
    NEVER = "never"
    SIDE_EFFECTS = "side_effects"
    HIGH_RISK = "high_risk"
    ALWAYS = "always"


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str = "personal"
    principal_id: str = "owner"
    roles: tuple[str, ...] = ("owner",)


@dataclass(frozen=True)
class SecurityPolicy:
    approval_policy: ApprovalPolicy = ApprovalPolicy.HIGH_RISK
    allowed_tools: tuple[str, ...] = ()
    denied_tools: tuple[str, ...] = ()
    allow_network: bool = True
    allow_shell: bool = False
    allow_self_mutation: bool = False
    audit_required: bool = True


@dataclass(frozen=True)
class PlatformConfig:
    """Production-oriented defaults for a single-user deployment."""

    postgres_dsn: str | None = None
    require_postgres: bool = True
    artifact_root: str = "./var/artifacts"
    approval_policy: ApprovalPolicy = ApprovalPolicy.HIGH_RISK
    enable_semantic_world: bool = True
    enable_learning: bool = True
    enable_federation: bool = False
    multi_tenant: bool = False


@dataclass(frozen=True)
class Approval:
    approval_id: str
    execution_id: str
    requested_at: str
    requested_by: str
    reason: str
    risk: str
    status: str = "pending"
    decided_at: str | None = None
    decided_by: str | None = None


@dataclass(frozen=True)
class ExecutionRecord:
    execution_id: str
    tenant_id: str
    objective: str
    status: str
    workflow_id: str | None = None
    capability_id: str | None = None
    agent_id: str | None = None
    model_id: str | None = None
    approval_id: str | None = None
    evidence_refs: tuple[str, ...] = ()
    validation: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class BackupManifest:
    backup_id: str
    created_at: str
    tenant_id: str
    schema_version: int
    included_domains: tuple[str, ...]
    artifact_root: str
    checksum: str | None = None


class DurableStore(Protocol):
    def initialize(self) -> None: ...


class ApprovalStore(Protocol):
    def put(self, approval: Approval) -> None: ...
    def get(self, approval_id: str) -> Approval | None: ...


class EvidenceSink(Protocol):
    def append(self, event: dict[str, Any]) -> str: ...


class PersonalPlatform:
    """Application-level composition root for OIS personal use.

    The kernel remains authoritative for execution semantics. This class owns
    cross-cutting application state: sessions, approvals, traces, knowledge,
    memory, semantic entities, learning candidates, and federation boundaries.
    Provider adapters can be injected as the corresponding protocols mature.
    """

    def __init__(
        self,
        *,
        config: PlatformConfig | None = None,
        durable_store: DurableStore | None = None,
        tenant: TenantContext | None = None,
        security: SecurityPolicy | None = None,
    ) -> None:
        self.config = config or PlatformConfig()
        self.tenant = tenant or TenantContext()
        self.security = security or SecurityPolicy(
            approval_policy=self.config.approval_policy
        )
        self.durable_store = durable_store
        self.executions: dict[str, ExecutionRecord] = {}
        self.approvals: dict[str, Approval] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.knowledge: dict[str, dict[str, Any]] = {}
        self.memory: dict[str, dict[str, Any]] = {}
        self.entities: dict[str, dict[str, Any]] = {}
        self.relationships: list[dict[str, Any]] = []
        self.learning_candidates: dict[str, dict[str, Any]] = {}
        self.traces: list[dict[str, Any]] = []
        self.federation_peers: dict[str, dict[str, Any]] = {}

        if self.config.require_postgres and self.durable_store is None:
            raise RuntimeError(
                "PersonalPlatform requires a durable PostgreSQL adapter; "
                "inject PostgresDurableExecutionStore for runtime use."
            )

    def initialize(self) -> None:
        if self.durable_store is not None:
            self.durable_store.initialize()

    def open_session(self, session_id: str | None = None) -> str:
        sid = session_id or str(uuid4())
        self.sessions[sid] = {
            "session_id": sid,
            "tenant_id": self.tenant.tenant_id,
            "principal_id": self.tenant.principal_id,
            "status": "active",
            "created_at": datetime.now(UTC).isoformat(),
        }
        return sid

    def create_execution(self, objective: str, **metadata: Any) -> ExecutionRecord:
        execution_id = str(uuid4())
        record = ExecutionRecord(
            execution_id=execution_id,
            tenant_id=self.tenant.tenant_id,
            objective=objective,
            status="created",
            workflow_id=metadata.get("workflow_id"),
            capability_id=metadata.get("capability_id"),
            agent_id=metadata.get("agent_id"),
            model_id=metadata.get("model_id"),
        )
        self.executions[execution_id] = record
        self.trace(execution_id, "execution.created", {"objective": objective})
        return record

    def request_approval(self, execution_id: str, reason: str, risk: str) -> Approval:
        approval = Approval(
            approval_id=str(uuid4()),
            execution_id=execution_id,
            requested_at=datetime.now(UTC).isoformat(),
            requested_by=self.tenant.principal_id,
            reason=reason,
            risk=risk,
        )
        self.approvals[approval.approval_id] = approval
        self.trace(execution_id, "approval.requested", approval.__dict__)
        return approval

    def decide_approval(self, approval_id: str, *, approved: bool) -> Approval:
        current = self.approvals[approval_id]
        if current.status != "pending":
            raise ValueError("approval is already decided")
        status = "approved" if approved else "rejected"
        updated = Approval(
            **{**current.__dict__, "status": status,
               "decided_at": datetime.now(UTC).isoformat(),
               "decided_by": self.tenant.principal_id}
        )
        self.approvals[approval_id] = updated
        self.trace(current.execution_id, "approval.decided", {"status": status})
        return updated

    def record_knowledge(self, ref_id: str, payload: dict[str, Any]) -> None:
        self.knowledge[ref_id] = {**payload, "ref_id": ref_id, "tenant_id": self.tenant.tenant_id}

    def remember(self, ref_id: str, payload: dict[str, Any], *, memory_type: str) -> None:
        self.memory[ref_id] = {
            **payload, "ref_id": ref_id, "memory_type": memory_type,
            "tenant_id": self.tenant.tenant_id,
            "recorded_at": datetime.now(UTC).isoformat(),
        }

    def add_entity(self, entity_id: str, entity_type: str, **attributes: Any) -> None:
        self.entities[entity_id] = {
            "entity_id": entity_id, "entity_type": entity_type,
            "attributes": dict(attributes), "tenant_id": self.tenant.tenant_id,
        }

    def relate(self, source: str, relation: str, target: str, **metadata: Any) -> None:
        if source not in self.entities or target not in self.entities:
            raise KeyError("semantic relationship requires registered entities")
        self.relationships.append({
            "source": source, "relation": relation, "target": target,
            "metadata": dict(metadata), "tenant_id": self.tenant.tenant_id,
        })

    def propose_learning(self, candidate_id: str, hypothesis: str, evidence_refs: list[str]) -> None:
        self.learning_candidates[candidate_id] = {
            "candidate_id": candidate_id, "hypothesis": hypothesis,
            "evidence_refs": list(evidence_refs), "state": "candidate",
            "tenant_id": self.tenant.tenant_id,
        }

    def promote_learning(self, candidate_id: str, *, approved: bool, evaluation: dict[str, Any]) -> None:
        candidate = self.learning_candidates[candidate_id]
        if not approved:
            candidate["state"] = "rejected"
            return
        if not evaluation.get("passed"):
            raise ValueError("learning promotion requires a passing evaluation")
        candidate["state"] = "promoted"
        candidate["promoted_at"] = datetime.now(UTC).isoformat()
        candidate["evaluation"] = dict(evaluation)

    def register_federation_peer(self, peer_id: str, endpoint: str, capabilities: list[str]) -> None:
        if not self.config.enable_federation:
            raise PermissionError("agent federation is disabled by configuration")
        self.federation_peers[peer_id] = {
            "peer_id": peer_id, "endpoint": endpoint,
            "capabilities": list(capabilities), "status": "registered",
        }

    def trace(self, execution_id: str, event: str, payload: dict[str, Any]) -> None:
        self.traces.append({
            "execution_id": execution_id, "tenant_id": self.tenant.tenant_id,
            "event": event, "payload": dict(payload),
            "timestamp": datetime.now(UTC).isoformat(),
        })

    def health(self) -> dict[str, Any]:
        return {
            "status": "ready" if self.durable_store is not None else "blocked",
            "tenant_id": self.tenant.tenant_id,
            "postgres_configured": self.durable_store is not None,
            "execution_count": len(self.executions),
            "pending_approvals": sum(a.status == "pending" for a in self.approvals.values()),
            "knowledge_items": len(self.knowledge),
            "memory_items": len(self.memory),
            "semantic_entities": len(self.entities),
            "learning_candidates": len(self.learning_candidates),
            "federation_peers": len(self.federation_peers),
        }

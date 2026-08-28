"""Production governance primitives for OIS controlled activation.

These are deterministic control-plane components. They do not claim that a
cloud deployment or external production service is live; adapters must supply
real deployment and telemetry evidence before activation can be promoted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Protocol
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(value: Any) -> str:
    return sha256(repr(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Subject:
    subject_id: str
    tenant_id: str
    roles: frozenset[str] = frozenset()
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorizationPolicy:
    permission: str
    required_role: str | None = None
    required_attributes: dict[str, str] = field(default_factory=dict)


class AuthorizationError(PermissionError):
    pass


class RBACABAC:
    """Deny-by-default authorization combining RBAC and ABAC."""

    def authorize(self, subject: Subject, policy: AuthorizationPolicy) -> None:
        if not subject.tenant_id:
            raise AuthorizationError("tenant identity is required")
        if policy.required_role and policy.required_role not in subject.roles:
            raise AuthorizationError("required role is missing")
        for key, expected in policy.required_attributes.items():
            if subject.attributes.get(key) != expected:
                raise AuthorizationError(f"required attribute is missing: {key}")


@dataclass(frozen=True)
class EvidenceEvent:
    event_id: str
    execution_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime
    previous_hash: str | None
    content_hash: str


class EvidenceLedger:
    """Append-only, hash-linked evidence ledger."""

    def __init__(self) -> None:
        self._events: list[EvidenceEvent] = []
        self._ids: set[str] = set()

    def append(self, execution_id: str, event_type: str, payload: dict[str, Any]) -> EvidenceEvent:
        event_id = str(uuid4())
        if event_id in self._ids:
            raise ValueError("duplicate evidence event")
        previous = self._events[-1].content_hash if self._events else None
        content_hash = _digest((event_id, execution_id, event_type, payload, previous))
        event = EvidenceEvent(event_id, execution_id, event_type, dict(payload), _now(), previous, content_hash)
        self._events.append(event)
        self._ids.add(event_id)
        return event

    def events(self, execution_id: str | None = None) -> tuple[EvidenceEvent, ...]:
        if execution_id is None:
            return tuple(self._events)
        return tuple(e for e in self._events if e.execution_id == execution_id)

    def verify_chain(self) -> bool:
        previous = None
        for event in self._events:
            expected = _digest((event.event_id, event.execution_id, event.event_type, event.payload, previous))
            if event.previous_hash != previous or event.content_hash != expected:
                return False
            previous = event.content_hash
        return True


@dataclass(frozen=True)
class DeploymentRecord:
    deployment_id: str
    candidate_version: str
    previous_version: str | None
    environment: str
    state: str
    evidence_ids: tuple[str, ...]


class DeploymentAdapter(Protocol):
    def deploy(self, version: str, environment: str) -> str: ...
    def rollback(self, version: str, environment: str) -> str: ...


class InMemoryDeploymentAdapter:
    """Deterministic adapter used for contract/integration tests."""

    def __init__(self) -> None:
        self.active: dict[str, str] = {}

    def deploy(self, version: str, environment: str) -> str:
        self.active[environment] = version
        return version

    def rollback(self, version: str, environment: str) -> str:
        self.active[environment] = version
        return version


class ProductionControlPlane:
    def __init__(self, *, authorization: RBACABAC, evidence: EvidenceLedger, deployment: DeploymentAdapter) -> None:
        self.authorization = authorization
        self.evidence = evidence
        self.deployment = deployment

    def activate(self, subject: Subject, candidate: str, environment: str, *, previous: str | None = None) -> DeploymentRecord:
        self.authorization.authorize(subject, AuthorizationPolicy("deployment.activate", "release-manager", {"environment": environment}))
        execution_id = str(uuid4())
        event = self.evidence.append(execution_id, "deployment.approval", {"candidate": candidate, "environment": environment})
        if not event:
            raise RuntimeError("approval evidence was not recorded")
        self.deployment.deploy(candidate, environment)
        self.evidence.append(execution_id, "deployment.activated", {"candidate": candidate, "environment": environment})
        return DeploymentRecord(str(uuid4()), candidate, previous, environment, "ACTIVE", tuple(e.event_id for e in self.evidence.events(execution_id)))

    def rollback(self, subject: Subject, target: str, environment: str) -> DeploymentRecord:
        self.authorization.authorize(subject, AuthorizationPolicy("deployment.rollback", "release-manager", {"environment": environment}))
        execution_id = str(uuid4())
        self.evidence.append(execution_id, "deployment.rollback.approved", {"target": target, "environment": environment})
        self.deployment.rollback(target, environment)
        self.evidence.append(execution_id, "deployment.rollback.verified", {"target": target, "environment": environment})
        return DeploymentRecord(str(uuid4()), target, None, environment, "ROLLED_BACK", tuple(e.event_id for e in self.evidence.events(execution_id)))

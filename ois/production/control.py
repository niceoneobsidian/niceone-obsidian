"""Governed production primitives for deployment, evolution, and intelligence.

These components deliberately stop at explicit external boundaries. They provide
executable control and evidence contracts; platform credentials, infrastructure,
and human approval remain deployment concerns.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


class GovernanceError(RuntimeError):
    """Raised when a governed production transition is invalid."""


@dataclass(frozen=True)
class AuthorizationContext:
    subject: str
    tenant: str
    roles: frozenset[str] = frozenset()
    attributes: dict[str, str] = field(default_factory=dict)
    permissions: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ABACRule:
    permission: str
    roles: frozenset[str] = frozenset()
    attributes: dict[str, str] = field(default_factory=dict)
    tenant_required: bool = True

    def allows(self, context: AuthorizationContext) -> bool:
        if self.tenant_required and not context.tenant:
            return False
        if self.roles and not self.roles.intersection(context.roles):
            return False
        if any(context.attributes.get(k) != v for k, v in self.attributes.items()):
            return False
        return self.permission in context.permissions


class EnterpriseAuthorizer:
    """Small deny-by-default RBAC + ABAC evaluator suitable for the kernel boundary."""

    def __init__(self, rules: tuple[ABACRule, ...] = ()) -> None:
        self._rules = rules

    def authorize(self, context: AuthorizationContext, permission: str) -> bool:
        candidates = tuple(rule for rule in self._rules if rule.permission == permission)
        if not candidates or not any(rule.allows(context) for rule in candidates):
            raise GovernanceError(f"authorization denied: {permission}")
        return True


@dataclass(frozen=True)
class DeploymentRecord:
    deployment_id: str
    version: str
    environment: str
    previous_version: str | None
    state: str
    approved_by: str | None
    evidence: tuple[str, ...] = ()


class DeploymentController:
    """Versioned activation controller with explicit approval and rollback evidence."""

    def __init__(self) -> None:
        self._current: dict[str, str] = {}
        self._records: list[DeploymentRecord] = []

    def deploy(
        self,
        version: str,
        environment: str,
        *,
        approved_by: str | None = None,
        evidence: tuple[str, ...] = (),
    ) -> DeploymentRecord:
        if not approved_by:
            raise GovernanceError("deployment requires explicit approval")
        if not evidence:
            raise GovernanceError("deployment requires evidence")
        previous = self._current.get(environment)
        record = DeploymentRecord(
            str(uuid.uuid4()), version, environment, previous, "active", approved_by, evidence
        )
        self._current[environment] = version
        self._records.append(record)
        return record

    def rollback(
        self, environment: str, *, approved_by: str | None = None, evidence: tuple[str, ...] = ()
    ) -> DeploymentRecord:
        if not approved_by:
            raise GovernanceError("rollback requires explicit approval")
        if not evidence:
            raise GovernanceError("rollback requires evidence")
        previous = self._previous(environment)
        current = self._current.get(environment)
        if previous is None:
            raise GovernanceError("no rollback target exists")
        record = DeploymentRecord(
            str(uuid.uuid4()), previous, environment, current, "rolled_back", approved_by, evidence
        )
        self._current[environment] = previous
        self._records.append(record)
        return record

    def current(self, environment: str) -> str | None:
        return self._current.get(environment)

    def history(self, environment: str) -> tuple[DeploymentRecord, ...]:
        return tuple(r for r in self._records if r.environment == environment)

    def _previous(self, environment: str) -> str | None:
        history = self.history(environment)
        if len(history) < 1:
            return None
        current = history[-1].version
        for record in reversed(history[:-1]):
            if record.version != current:
                return record.version
        return history[-1].previous_version


class CanaryController:
    """Deterministic traffic assignment plus measurable promotion/rollback gates."""

    def __init__(self) -> None:
        self._rollouts: dict[str, dict[str, Any]] = {}

    def start(self, rollout_id: str, stable: str, candidate: str, percentage: int = 5) -> None:
        if not 1 <= percentage <= 100:
            raise GovernanceError("canary percentage must be between 1 and 100")
        self._rollouts[rollout_id] = {
            "stable": stable,
            "candidate": candidate,
            "percentage": percentage,
            "state": "canary",
        }

    def assign(self, rollout_id: str, subject: str) -> str:
        rollout = self._rollouts[rollout_id]
        bucket = int(hashlib.sha256(subject.encode()).hexdigest()[:8], 16) % 100
        return rollout["candidate"] if bucket < rollout["percentage"] else rollout["stable"]

    def decide(
        self,
        rollout_id: str,
        *,
        success_rate: float,
        latency_ratio: float,
        min_success_rate: float = 0.99,
        max_latency_ratio: float = 1.20,
        approved_by: str | None = None,
    ) -> str:
        rollout = self._rollouts[rollout_id]
        if not approved_by:
            raise GovernanceError("canary transition requires approval")
        if success_rate >= min_success_rate and latency_ratio <= max_latency_ratio:
            rollout["state"] = "promoted"
            return "promoted"
        rollout["state"] = "rolled_back"
        return "rolled_back"

    def state(self, rollout_id: str) -> str:
        return str(self._rollouts[rollout_id]["state"])


@dataclass(frozen=True)
class Lease:
    job_id: str
    worker_id: str
    expires_at: float


class DistributedCoordinator:
    """SQLite-backed lease/idempotency coordinator for multi-worker execution."""

    def __init__(self, database: str = ":memory:") -> None:
        self._db = sqlite3.connect(database)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, state TEXT NOT NULL, result TEXT)"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS leases (job_id TEXT PRIMARY KEY, worker_id TEXT NOT NULL, expires REAL NOT NULL)"
        )
        self._db.commit()

    def claim(self, job_id: str, worker_id: str, ttl_seconds: float = 30.0) -> Lease | None:
        now = time.time()
        row = self._db.execute(
            "SELECT worker_id, expires FROM leases WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row and row[1] > now and row[0] != worker_id:
            return None
        expires = now + ttl_seconds
        self._db.execute(
            "INSERT OR REPLACE INTO leases VALUES (?, ?, ?)", (job_id, worker_id, expires)
        )
        self._db.execute(
            "INSERT OR IGNORE INTO jobs(job_id, state) VALUES (?, 'claimed')", (job_id,)
        )
        self._db.commit()
        return Lease(job_id, worker_id, expires)

    def complete(self, job_id: str, worker_id: str, result: Any) -> None:
        row = self._db.execute(
            "SELECT worker_id FROM leases WHERE job_id = ?", (job_id,)
        ).fetchone()
        if not row or row[0] != worker_id:
            raise GovernanceError("worker does not own job lease")
        self._db.execute(
            "UPDATE jobs SET state = 'completed', result = ? WHERE job_id = ?",
            (json.dumps(result, sort_keys=True), job_id),
        )
        self._db.execute("DELETE FROM leases WHERE job_id = ?", (job_id,))
        self._db.commit()

    def result(self, job_id: str) -> Any | None:
        row = self._db.execute("SELECT result FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return None if not row or row[0] is None else json.loads(row[0])


class ExternalConnector(Protocol):
    """Governed external connector boundary; implementations must supply credentials safely."""

    name: str

    def send(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class HttpConnector:
    """Minimal outbound connector with an explicit allowlisted endpoint."""

    def __init__(self, name: str, endpoint: str, timeout: float = 10.0) -> None:
        if not endpoint.startswith("https://"):
            raise GovernanceError("external connectors require HTTPS")
        self.name = name
        self.endpoint = endpoint
        self.timeout = timeout

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = response.read().decode("utf-8")
        return {"status": "ok", "body": body}


class SemanticWorld:
    """Durable entity/fact graph with provenance and append-only fact history."""

    def __init__(self, database: str = ":memory:") -> None:
        self._db = sqlite3.connect(database)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, type TEXT NOT NULL, data TEXT NOT NULL)"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS facts (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL, predicate TEXT NOT NULL, object TEXT NOT NULL, source TEXT NOT NULL, version INTEGER NOT NULL)"
        )
        self._db.commit()

    def upsert_entity(self, entity_id: str, entity_type: str, data: dict[str, Any]) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO entities VALUES (?, ?, ?)",
            (entity_id, entity_type, json.dumps(data, sort_keys=True)),
        )
        self._db.commit()

    def add_fact(self, subject: str, predicate: str, obj: str, source: str) -> int:
        row = self._db.execute(
            "SELECT COALESCE(MAX(version), 0) FROM facts WHERE subject = ? AND predicate = ?",
            (subject, predicate),
        ).fetchone()
        version = int(row[0]) + 1
        cursor = self._db.execute(
            "INSERT INTO facts(subject,predicate,object,source,version) VALUES(?,?,?,?,?)",
            (subject, predicate, obj, source, version),
        )
        self._db.commit()
        return int(cursor.lastrowid)

    def facts(self, subject: str) -> tuple[dict[str, Any], ...]:
        rows = self._db.execute(
            "SELECT subject,predicate,object,source,version FROM facts WHERE subject = ? ORDER BY id",
            (subject,),
        ).fetchall()
        return tuple(
            {"subject": r[0], "predicate": r[1], "object": r[2], "source": r[3], "version": r[4]}
            for r in rows
        )


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    target: str
    version: str
    evidence: tuple[str, ...]
    state: str = "proposed"


class LearningEngine:
    """Evidence-gated learning loop: observe -> propose -> evaluate -> approve -> activate."""

    def __init__(self) -> None:
        self._candidates: dict[str, Candidate] = {}

    def propose(self, target: str, version: str, evidence: tuple[str, ...]) -> Candidate:
        if not evidence:
            raise GovernanceError("learning proposal requires evidence")
        candidate = Candidate(str(uuid.uuid4()), target, version, evidence)
        self._candidates[candidate.candidate_id] = candidate
        return candidate

    def evaluate(self, candidate_id: str, score: float) -> Candidate:
        candidate = self._candidates[candidate_id]
        state = "evaluated" if 0.0 <= score <= 1.0 else "rejected"
        updated = Candidate(
            candidate.candidate_id, candidate.target, candidate.version, candidate.evidence, state
        )
        self._candidates[candidate_id] = updated
        return updated

    def approve(self, candidate_id: str, *, approved_by: str) -> Candidate:
        candidate = self._candidates[candidate_id]
        if candidate.state != "evaluated":
            raise GovernanceError("candidate must be evaluated before approval")
        if not approved_by:
            raise GovernanceError("candidate approval requires identity")
        updated = Candidate(
            candidate.candidate_id,
            candidate.target,
            candidate.version,
            candidate.evidence,
            "approved",
        )
        self._candidates[candidate_id] = updated
        return updated

    def activate(self, candidate_id: str, *, rollout: Callable[[Candidate], None]) -> Candidate:
        candidate = self._candidates[candidate_id]
        if candidate.state != "approved":
            raise GovernanceError("only approved candidates may activate")
        rollout(candidate)
        updated = Candidate(
            candidate.candidate_id,
            candidate.target,
            candidate.version,
            candidate.evidence,
            "activated",
        )
        self._candidates[candidate_id] = updated
        return updated

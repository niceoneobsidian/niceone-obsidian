"""Operational security controls for OIS secret lifecycle.

These components provide deterministic control-plane contracts. Cloud writes and
identity attestations remain adapter responsibilities; no secret values are logged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from typing import Any, Iterable, Mapping, Protocol


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ProviderVersion:
    secret_id: str
    provider: str
    version: str
    state: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ReconciliationFinding:
    secret_id: str
    provider: str
    kind: str
    expected_version: str | None
    observed_version: str | None


class MetadataProvider(Protocol):
    name: str
    def list_versions(self) -> Iterable[ProviderVersion]: ...


class ProviderReconciler:
    """Reconcile version/state metadata only; never fetch secret payloads."""
    def reconcile(self, canonical: Iterable[ProviderVersion], providers: Iterable[MetadataProvider]) -> list[ReconciliationFinding]:
        expected = {x.secret_id: x for x in canonical}
        findings: list[ReconciliationFinding] = []
        for provider in providers:
            observed = {x.secret_id: x for x in provider.list_versions()}
            for secret_id in sorted(expected.keys() | observed.keys()):
                left, right = expected.get(secret_id), observed.get(secret_id)
                if left is None:
                    kind = "provider_orphan"
                elif right is None:
                    kind = "provider_missing"
                elif left.version != right.version:
                    kind = "version_drift"
                elif left.state != right.state:
                    kind = "state_drift"
                else:
                    continue
                findings.append(ReconciliationFinding(secret_id, provider.name, kind,
                    left.version if left else None, right.version if right else None))
        return findings


@dataclass(slots=True)
class DualKeyRotation:
    secret_id: str
    old_version: str
    new_version: str
    state: str = "prepared"
    created_at: str = field(default_factory=lambda: utcnow().isoformat())
    verified_consumers: set[str] = field(default_factory=set)

    def activate(self, consumers: Iterable[str], verifier) -> None:
        if self.state != "prepared":
            raise RuntimeError("rotation must be prepared before activation")
        required = set(consumers)
        if not required:
            raise ValueError("at least one consumer is required")
        passed = {consumer for consumer in required if verifier(consumer, self.new_version)}
        if passed != required:
            self.state = "verification_failed"
            raise RuntimeError("new credential failed consumer verification; old credential remains active")
        self.verified_consumers = passed
        self.state = "dual_active"

    def commit(self, revoke_old) -> None:
        if self.state != "dual_active":
            raise RuntimeError("both credentials must be active and verified before commit")
        if revoke_old(self.old_version) is not True:
            self.state = "revoke_pending"
            raise RuntimeError("old credential revocation not confirmed")
        self.state = "complete"


class RotationDependencyGraph:
    def __init__(self) -> None:
        self._dependencies: dict[str, set[str]] = {}

    def add(self, node: str, depends_on: Iterable[str] = ()) -> None:
        self._dependencies.setdefault(node, set()).update(depends_on)
        for dep in depends_on:
            self._dependencies.setdefault(dep, set())

    def order(self) -> list[str]:
        pending = {k: set(v) for k, v in self._dependencies.items()}
        ready = sorted(k for k, deps in pending.items() if not deps)
        ordered: list[str] = []
        while ready:
            node = ready.pop(0)
            ordered.append(node)
            for key in sorted(pending):
                if node in pending[key]:
                    pending[key].remove(node)
                    if not pending[key] and key not in ordered and key not in ready:
                        ready.append(key)
            ready.sort()
        if len(ordered) != len(pending):
            raise ValueError("rotation dependency cycle detected")
        return ordered


@dataclass(frozen=True, slots=True)
class SecuritySignal:
    subject: str
    kind: str
    timestamp: str
    risk: int
    source: str
    attributes: Mapping[str, str] = field(default_factory=dict)


class CredentialCompromiseCorrelator:
    def correlate(self, signals: Iterable[SecuritySignal], window: timedelta = timedelta(minutes=30)) -> list[dict[str, Any]]:
        grouped: dict[str, list[SecuritySignal]] = {}
        for signal in signals:
            grouped.setdefault(signal.subject, []).append(signal)
        incidents = []
        for subject, items in grouped.items():
            items.sort(key=lambda x: x.timestamp)
            kinds = {x.kind for x in items}
            if len(kinds) < 2:
                continue
            try:
                start = datetime.fromisoformat(items[0].timestamp)
                end = datetime.fromisoformat(items[-1].timestamp)
            except ValueError:
                continue
            if end - start <= window:
                incidents.append({"subject": subject, "signal_kinds": sorted(kinds),
                    "risk": min(100, max(x.risk for x in items) + 10 * (len(kinds) - 1)),
                    "signal_count": len(items), "sources": sorted({x.source for x in items})})
        return incidents


class ExternalEvidenceSink(Protocol):
    def put_immutable(self, key: str, payload: bytes, digest: str) -> str: ...


class ImmutableEvidenceExporter:
    """Hash and sign evidence before delegating immutable storage to a WORM-capable sink."""
    def __init__(self, sink: ExternalEvidenceSink, signing_key: bytes) -> None:
        if len(signing_key) < 32:
            raise ValueError("evidence signing key must be at least 32 bytes")
        self.sink, self.signing_key = sink, signing_key

    def export(self, event_id: str, evidence: Mapping[str, Any]) -> dict[str, str]:
        payload = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(payload).hexdigest()
        signature = hmac.new(self.signing_key, digest.encode(), hashlib.sha256).hexdigest()
        uri = self.sink.put_immutable(event_id, payload, digest)
        return {"event_id": event_id, "sha256": digest, "signature": signature, "uri": uri}


@dataclass(frozen=True, slots=True)
class AccessObservation:
    principal: str
    timestamp: str
    action: str
    outcome: str
    region: str | None = None
    device_id: str | None = None
    workload_id: str | None = None


class BehavioralAnomalyEngine:
    def __init__(self, known_regions: Mapping[str, set[str]] | None = None,
                 known_devices: Mapping[str, set[str]] | None = None) -> None:
        self.known_regions = dict(known_regions or {})
        self.known_devices = dict(known_devices or {})

    def score(self, observation: AccessObservation, recent: Iterable[AccessObservation] = ()) -> dict[str, Any]:
        history = list(recent)
        score, reasons = 0, []
        if observation.region and self.known_regions.get(observation.principal) and observation.region not in self.known_regions[observation.principal]:
            score += 35; reasons.append("new_region")
        if observation.device_id and self.known_devices.get(observation.principal) and observation.device_id not in self.known_devices[observation.principal]:
            score += 30; reasons.append("new_device")
        denied = sum(x.outcome.lower() == "deny" for x in history)
        if denied >= 5:
            score += 20; reasons.append("repeated_denials")
        if sum(x.action == observation.action for x in history) >= 50:
            score += 20; reasons.append("high_action_volume")
        if observation.outcome.lower() == "deny":
            score += 5
        return {"principal": observation.principal, "score": min(score, 100), "reasons": reasons,
                "decision": "escalate" if score >= 70 else "review" if score >= 35 else "allow_with_monitoring"}


@dataclass(frozen=True, slots=True)
class DeploymentCredentialBoundary:
    environment: str
    workload_identity: str
    allowed_providers: frozenset[str]
    require_federated_identity: bool = True
    forbid_static_cloud_keys: bool = True

    def validate(self, *, environment: str, workload_identity: str | None, provider: str, static_cloud_key: bool = False) -> None:
        if environment != self.environment:
            raise PermissionError("deployment environment mismatch")
        if provider not in self.allowed_providers:
            raise PermissionError("provider not allowed in deployment boundary")
        if self.require_federated_identity and not workload_identity:
            raise PermissionError("federated workload identity required")
        if self.workload_identity and workload_identity != self.workload_identity:
            raise PermissionError("workload identity mismatch")
        if self.forbid_static_cloud_keys and static_cloud_key:
            raise PermissionError("static cloud credentials prohibited")


@dataclass(frozen=True, slots=True)
class LifecyclePolicy:
    name: str
    interval_seconds: int
    action: str
    enabled: bool = True


class LifecycleScheduler:
    """Deterministic due-work planner; execution must be wired to approved OIS jobs."""
    def due(self, policies: Iterable[LifecyclePolicy], last_run: Mapping[str, datetime], now: datetime | None = None) -> list[LifecyclePolicy]:
        now = now or utcnow()
        return [p for p in policies if p.enabled and
                (p.name not in last_run or (now - last_run[p.name]).total_seconds() >= p.interval_seconds)]


@dataclass(frozen=True, slots=True)
class RecoveryExercise:
    name: str
    rpo_seconds: int
    rto_seconds: int
    backup_verified: bool
    restore_verified: bool
    measured_data_loss_seconds: int
    measured_recovery_seconds: int

    def evaluate(self) -> dict[str, Any]:
        passed = (self.backup_verified and self.restore_verified and
                  self.measured_data_loss_seconds <= self.rpo_seconds and
                  self.measured_recovery_seconds <= self.rto_seconds)
        return {"name": self.name, "passed": passed,
                "rpo_met": self.measured_data_loss_seconds <= self.rpo_seconds,
                "rto_met": self.measured_recovery_seconds <= self.rto_seconds}


@dataclass(frozen=True, slots=True)
class ComplianceControl:
    control_id: str
    description: str
    implementation_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    automated: bool = False


class ComplianceMapper:
    def evaluate(self, controls: Iterable[ComplianceControl]) -> list[dict[str, Any]]:
        return [{"control_id": c.control_id, "implemented": bool(c.implementation_refs),
                 "evidence_available": bool(c.evidence_refs), "automated": c.automated,
                 "status": "supported" if c.implementation_refs and c.evidence_refs else "gap"}
                for c in controls]


class CredentialRiskEngine:
    def score(self, *, age_days: int, exposure_signals: int = 0, unused_days: int = 0,
              privilege_level: int = 0, anomalous_access: int = 0, provider_drift: int = 0) -> dict[str, Any]:
        score = min(100, max(0, age_days // 30 * 5) + exposure_signals * 35 +
                    min(20, unused_days // 30 * 5) + privilege_level * 10 +
                    anomalous_access * 20 + provider_drift * 15)
        action = "quarantine_and_escalate" if score >= 80 else "review_and_rotate" if score >= 50 else "monitor"
        return {"score": score, "action": action, "automatic_destructive_action": False}


class AttackPathAnalyzer:
    """Find paths from principals to protected assets across directed access edges."""
    def paths(self, edges: Mapping[str, Iterable[str]], starts: Iterable[str], targets: set[str], max_depth: int = 8) -> list[list[str]]:
        found: list[list[str]] = []
        for start in starts:
            stack = [(start, [start])]
            while stack:
                node, path = stack.pop()
                if node in targets and len(path) > 1:
                    found.append(path); continue
                if len(path) - 1 >= max_depth:
                    continue
                for nxt in edges.get(node, ()):
                    if nxt not in path:
                        stack.append((nxt, path + [nxt]))
        return found


class SecurityDriftDetector:
    def __init__(self, baseline: Mapping[str, str]) -> None:
        self.baseline = dict(baseline)

    def compare(self, current: Mapping[str, str]) -> list[dict[str, str]]:
        keys = self.baseline.keys() | current.keys()
        return [{"control": k, "expected": self.baseline.get(k, "<missing>"),
                 "observed": current.get(k, "<missing>")}
                for k in sorted(keys) if self.baseline.get(k) != current.get(k)]


class HashChainedFileSink:
    """Local development sink only; production must use object-lock/WORM storage."""
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def put_immutable(self, key: str, payload: bytes, digest: str) -> str:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {"key": key, "payload_hex": payload.hex(), "sha256": digest}
        with self._lock:
            with self.path.open("ab") as stream:
                stream.write(json.dumps(record, sort_keys=True).encode() + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
        return str(self.path)

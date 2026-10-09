from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ois.security.secrets.lifecycle_ops import (
    AccessObservation, AttackPathAnalyzer, BehavioralAnomalyEngine,
    ComplianceControl, ComplianceMapper, CredentialCompromiseCorrelator,
    CredentialRiskEngine, DualKeyRotation, ProviderReconciler,
    ProviderVersion, RecoveryExercise, RotationDependencyGraph,
    SecurityDriftDetector, SecuritySignal,
)


class FakeProvider:
    name = "vault"
    def list_versions(self):
        return [ProviderVersion("db", "vault", "v2", "active", "now"),
                ProviderVersion("orphan", "vault", "v1", "active", "now")]


def test_provider_reconciliation_detects_version_and_orphan_drift():
    canonical = [ProviderVersion("db", "canonical", "v1", "active", "now"),
                 ProviderVersion("missing", "canonical", "v1", "active", "now")]
    findings = ProviderReconciler().reconcile(canonical, [FakeProvider()])
    assert {x.kind for x in findings} == {"version_drift", "provider_orphan", "provider_missing"}


def test_dual_key_rotation_requires_all_consumers_verified():
    rotation = DualKeyRotation("db", "old", "new")
    with pytest.raises(RuntimeError):
        rotation.activate(["api", "worker"], lambda consumer, version: consumer == "api")
    assert rotation.state == "verification_failed"


def test_dual_key_rotation_commits_only_after_verified_dual_active():
    rotation = DualKeyRotation("db", "old", "new")
    rotation.state = "prepared"
    rotation.activate(["api"], lambda consumer, version: version == "new")
    with pytest.raises(RuntimeError):
        rotation.commit(lambda version: False)
    assert rotation.state == "revoke_pending"


def test_rotation_graph_order_and_cycle_detection():
    graph = RotationDependencyGraph()
    graph.add("database")
    graph.add("api", ["database"])
    graph.add("worker", ["api"])
    assert graph.order() == ["database", "api", "worker"]
    graph.add("database", ["worker"])
    with pytest.raises(ValueError):
        graph.order()


def test_compromise_correlation_groups_distinct_signal_types():
    now = datetime.now(UTC)
    signals = [
        SecuritySignal("key-1", "new_device", now.isoformat(), 40, "auth"),
        SecuritySignal("key-1", "high_volume", (now + timedelta(minutes=2)).isoformat(), 50, "api"),
    ]
    incidents = CredentialCompromiseCorrelator().correlate(signals)
    assert len(incidents) == 1 and incidents[0]["risk"] == 60


def test_behavioral_anomaly_uses_geo_device_and_denials():
    engine = BehavioralAnomalyEngine({"alice": {"NG"}}, {"alice": {"laptop"}})
    obs = AccessObservation("alice", datetime.now(UTC).isoformat(), "secret.read", "deny", "US", "phone")
    history = [AccessObservation("alice", obs.timestamp, "x", "deny") for _ in range(5)]
    result = engine.score(obs, history)
    assert result["score"] >= 70
    assert result["decision"] == "escalate"


def test_risk_engine_and_drift_detector():
    risk = CredentialRiskEngine().score(age_days=365, exposure_signals=1, anomalous_access=2)
    assert risk["score"] == 100
    assert risk["automatic_destructive_action"] is False
    assert SecurityDriftDetector({"gitleaks": "enabled"}).compare({"gitleaks": "disabled"})[0]["control"] == "gitleaks"


def test_attack_path_analysis_and_compliance_gaps():
    paths = AttackPathAnalyzer().paths({"agent": ["service"], "service": ["database"]}, ["agent"], {"database"})
    assert paths == [["agent", "service", "database"]]
    rows = ComplianceMapper().evaluate([
        ComplianceControl("SEC-1", "scan", ("scanner.py",), ("ci-run",), True),
        ComplianceControl("SEC-2", "audit", (), ()),
    ])
    assert [x["status"] for x in rows] == ["supported", "gap"]


def test_recovery_exercise_checks_rpo_rto_and_restore():
    result = RecoveryExercise("nightly", 60, 300, True, True, 30, 240).evaluate()
    assert result["passed"] is True
    failed = RecoveryExercise("nightly", 60, 300, True, False, 30, 240).evaluate()
    assert failed["passed"] is False

from __future__ import annotations

from production.control_plane import EvidenceLedger, InMemoryDeploymentAdapter, ProductionControlPlane, RBACABAC, Subject
from production.evolution import CanaryController, Measurement
from production.rollout import RolloutController


def release_operator() -> Subject:
    return Subject("release-1", "tenant-1", frozenset({"release-manager"}), {"environment": "staging"})


def test_failed_canary_rolls_back_and_records_evidence() -> None:
    ledger = EvidenceLedger()
    adapter = InMemoryDeploymentAdapter()
    control = ProductionControlPlane(authorization=RBACABAC(), evidence=ledger, deployment=adapter)
    rollout = RolloutController(control, CanaryController(minimum_success_rate=0.99, maximum_latency_ms=500), ledger)

    result = rollout.evaluate_and_rollout(
        release_operator(), "v2", "staging", previous="v1", traffic_percent=5,
        successes=95, total=100, latency_ms=800,
    )
    assert result.state == "ROLLED_BACK"
    assert adapter.active["staging"] == "v1"
    assert any(e.event_type == "rollout.canary.failed" for e in ledger.events("rollout:v2:staging"))
    assert ledger.verify_chain()


def test_healthy_canary_promotes_and_records_measurement() -> None:
    ledger = EvidenceLedger()
    adapter = InMemoryDeploymentAdapter()
    control = ProductionControlPlane(authorization=RBACABAC(), evidence=ledger, deployment=adapter)
    rollout = RolloutController(control, CanaryController(minimum_success_rate=0.99, maximum_latency_ms=500), ledger)

    result = rollout.evaluate_and_rollout(
        release_operator(), "v3", "staging", previous="v1", traffic_percent=5,
        successes=100, total=100, latency_ms=120,
        measurements=[Measurement("reward", 0.92)],
    )
    assert result.state == "PROMOTED"
    assert adapter.active["staging"] == "v3"
    events = ledger.events("rollout:v3:staging")
    assert any(e.event_type == "rollout.canary.passed" for e in events)
    assert any(e.event_type == "rollout.promoted" for e in events)
    assert ledger.verify_chain()

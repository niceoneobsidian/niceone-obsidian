from __future__ import annotations

from production.control_plane import (
    AuthorizationError,
    AuthorizationPolicy,
    EvidenceLedger,
    InMemoryDeploymentAdapter,
    ProductionControlPlane,
    RBACABAC,
    Subject,
)
from production.evolution import CanaryController, LearningLoop, Measurement
from production.semantic_world import SemanticWorld
from production.workers import LeaseQueue, Worker


def operator(environment: str = "staging") -> Subject:
    return Subject("release-1", "tenant-1", frozenset({"release-manager"}), {"environment": environment})


def test_evidence_ledger_is_hash_linked() -> None:
    ledger = EvidenceLedger()
    ledger.append("exec-1", "execution.started", {"version": "1"})
    ledger.append("exec-1", "execution.succeeded", {"version": "1"})
    assert ledger.verify_chain()
    assert len(ledger.events("exec-1")) == 2


def test_production_activation_requires_rbac_abac() -> None:
    ledger = EvidenceLedger()
    cp = ProductionControlPlane(authorization=RBACABAC(), evidence=ledger, deployment=InMemoryDeploymentAdapter())
    denied = Subject("viewer", "tenant-1", frozenset({"viewer"}), {"environment": "staging"})
    try:
        cp.activate(denied, "v2", "staging")
    except AuthorizationError:
        pass
    else:
        raise AssertionError("activation must be denied")


def test_activation_and_rollback_are_evidenced() -> None:
    ledger = EvidenceLedger()
    adapter = InMemoryDeploymentAdapter()
    cp = ProductionControlPlane(authorization=RBACABAC(), evidence=ledger, deployment=adapter)
    active = cp.activate(operator(), "v2", "staging", previous="v1")
    assert active.state == "ACTIVE"
    assert adapter.active["staging"] == "v2"
    rolled = cp.rollback(operator(), "v1", "staging")
    assert rolled.state == "ROLLED_BACK"
    assert adapter.active["staging"] == "v1"
    assert ledger.verify_chain()


def test_distributed_lease_allows_single_owner_and_recovers() -> None:
    queue = LeaseQueue(lease_seconds=60, max_attempts=2)
    work_id = queue.enqueue({"value": 7})
    first = queue.claim("worker-a")
    assert first and first.work_id == work_id
    assert queue.claim("worker-b") is None
    assert queue.heartbeat(work_id, "worker-b") is False
    assert queue.complete(work_id, "worker-a", 49)
    assert queue.get(work_id).result == 49


def test_worker_failure_requeues_for_retry() -> None:
    queue = LeaseQueue(max_attempts=2)
    queue.enqueue({"fail": True})
    calls = {"n": 0}

    def handler(payload):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("deliberate failure")
        return "recovered"

    worker = Worker("worker-a", queue, handler)
    assert worker.run_once()
    assert worker.run_once()
    item = next(i for i in (queue.get(work_id) for work_id in []) if i)
    assert item is None


def test_semantic_world_requires_provenance_and_versions_facts() -> None:
    world = SemanticWorld()
    entity = world.upsert_entity("campaign", {"name": "OIS"})
    first = world.assert_fact(entity.entity_id, "status", "active", source="execution:1")
    second = world.assert_fact(entity.entity_id, "status", "paused", source="execution:2")
    assert first.version == 1
    assert second.version == 2
    assert world.facts(entity.entity_id, "status")[-1].object_value == "paused"


def test_canary_failure_and_learning_gate() -> None:
    canary = CanaryController(minimum_success_rate=0.99, maximum_latency_ms=500)
    failed = canary.decide("v2", 5, successes=95, total=100, latency_ms=600)
    assert not failed.passed
    loop = LearningLoop()
    evaluation = loop.evaluate("strategy-v2", [Measurement("reward", 0.8)], baseline=0.7, minimum_score=0.75)
    assert evaluation.passed
    assert loop.candidate("strategy-v2", evaluation) == "PENDING_APPROVAL"
    assert loop.candidate("strategy-v2", evaluation, approved=True) == "APPROVED"

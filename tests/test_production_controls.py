from ois.production import (
    ABACRule,
    AuthorizationContext,
    CanaryController,
    DeploymentController,
    DistributedCoordinator,
    GovernanceError,
    LearningEngine,
    SemanticWorld,
)


def test_rbac_abac_is_deny_by_default() -> None:
    authorizer = __import__(
        "ois.production.control", fromlist=["EnterpriseAuthorizer"]
    ).EnterpriseAuthorizer(rules=(ABACRule("deploy", frozenset({"release"}), {"env": "prod"}),))
    context = AuthorizationContext(
        "u1", "t1", frozenset({"release"}), {"env": "prod"}, frozenset({"deploy"})
    )
    assert authorizer.authorize(context, "deploy")
    bad = AuthorizationContext(
        "u2", "t1", frozenset({"viewer"}), {"env": "prod"}, frozenset({"deploy"})
    )
    try:
        authorizer.authorize(bad, "deploy")
    except GovernanceError:
        pass
    else:
        raise AssertionError("unauthorized context was accepted")


def test_deployment_requires_evidence_and_rolls_back() -> None:
    controller = DeploymentController()
    try:
        controller.deploy("v1", "prod", approved_by="release", evidence=())
    except GovernanceError:
        pass
    else:
        raise AssertionError("deployment without evidence was accepted")
    controller.deploy("v1", "prod", approved_by="release", evidence=("ci:green",))
    controller.deploy("v2", "prod", approved_by="release", evidence=("ci:green", "canary:pass"))
    assert controller.current("prod") == "v2"
    controller.rollback("prod", approved_by="release", evidence=("incident:42",))
    assert controller.current("prod") == "v1"


def test_canary_is_deterministic_and_rolls_back_on_bad_metrics() -> None:
    canary = CanaryController()
    canary.start("r1", "v1", "v2", 50)
    assert canary.assign("r1", "same-subject") == canary.assign("r1", "same-subject")
    assert (
        canary.decide("r1", success_rate=0.90, latency_ratio=1.1, approved_by="release")
        == "rolled_back"
    )


def test_distributed_lease_prevents_double_claim_and_is_idempotent() -> None:
    coordinator = DistributedCoordinator()
    assert coordinator.claim("job-1", "worker-a") is not None
    assert coordinator.claim("job-1", "worker-b") is None
    coordinator.complete("job-1", "worker-a", {"ok": True})
    assert coordinator.result("job-1") == {"ok": True}


def test_semantic_world_preserves_provenance_and_versions() -> None:
    world = SemanticWorld()
    world.upsert_entity("e1", "creator", {"name": "Ada"})
    world.add_fact("e1", "works_on", "ois", "source:a")
    world.add_fact("e1", "works_on", "ois-next", "source:b")
    facts = world.facts("e1")
    assert [f["version"] for f in facts] == [1, 2]
    assert facts[1]["source"] == "source:b"


def test_learning_loop_is_evidence_gated_and_requires_evaluation() -> None:
    learning = LearningEngine()
    candidate = learning.propose("planner", "v2", ("metric:123",))
    try:
        learning.activate(candidate.candidate_id, rollout=lambda _: None)
    except GovernanceError:
        pass
    else:
        raise AssertionError("unevaluated candidate activated")
    learning.evaluate(candidate.candidate_id, 0.97)
    learning.approve(candidate.candidate_id, approved_by="owner")
    activated = learning.activate(candidate.candidate_id, rollout=lambda _: None)
    assert activated.state == "activated"

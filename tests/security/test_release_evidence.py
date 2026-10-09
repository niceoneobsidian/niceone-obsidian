from production.control_plane import EvidenceLedger, InMemoryDeploymentAdapter, ProductionControlPlane, RBACABAC, Subject

def test_deployment_and_rollback_evidence() -> None:
    evidence = EvidenceLedger()
    plane = ProductionControlPlane(
        authorization=RBACABAC(),
        evidence=evidence,
        deployment=InMemoryDeploymentAdapter(),
    )
    subject = Subject(
        subject_id="release-test",
        tenant_id="test",
        roles=frozenset({"release-manager"}),
        attributes={"environment": "staging"},
    )
    activation = plane.activate(subject, "candidate-1", "staging", previous="previous-1")
    assert activation.state == "ACTIVE"
    rollback = plane.rollback(subject, "previous-1", "staging")
    assert rollback.state == "ROLLED_BACK"
    assert evidence.verify_chain()
    event_types = [event.event_type for event in evidence.events()]
    assert "deployment.activated" in event_types
    assert "deployment.rollback.verified" in event_types

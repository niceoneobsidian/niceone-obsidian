from ois.governance.promotion import (
    EvidencePromotionGate,
    EvidenceStatus,
    PromotionBlocked,
    PromotionEvidence,
)
from ois.kernel.types import FailureClass
from ois.supervisor.supervisor import (
    SupervisionAction,
    SupervisionRequest,
    Supervisor,
)


def test_supervisor_executes_only_after_validated_authorized_plan():
    decision = Supervisor().decide(
        SupervisionRequest(
            objective="run capability",
            plan_validated=True,
            authorized=True,
            status="planned",
        )
    )
    assert decision.action == SupervisionAction.EXECUTE


def test_supervisor_escalates_missing_approval():
    decision = Supervisor().decide(
        SupervisionRequest(
            objective="publish",
            plan_validated=True,
            authorized=True,
            status="planned",
            approval_required=True,
            approval_granted=False,
        )
    )
    assert decision.action == SupervisionAction.ESCALATE


def test_supervisor_stops_safety_failure():
    decision = Supervisor().decide(
        SupervisionRequest(
            objective="execute",
            plan_validated=True,
            authorized=True,
            status="failed",
            failure=FailureClass.SAFETY,
        )
    )
    assert decision.action == SupervisionAction.STOP


def test_supervisor_retries_only_when_recovery_policy_allows_it():
    decision = Supervisor().decide(
        SupervisionRequest(
            objective="execute",
            plan_validated=True,
            authorized=True,
            status="failed",
            failure=FailureClass.TRANSIENT,
            retry_allowed=True,
        )
    )
    assert decision.action == SupervisionAction.RETRY


def test_promotion_gate_blocks_missing_runtime_evidence():
    evidence = PromotionEvidence(
        implementation=True,
        tests=True,
        integration=True,
        runtime=False,
        security=True,
        observability=True,
        recovery=True,
        rollback=True,
        provenance=("ci://run/123",),
    )
    decision = EvidencePromotionGate().evaluate(evidence)
    assert decision.allowed is False
    assert decision.status == EvidenceStatus.INTEGRATED
    assert "runtime" in decision.missing


def test_promotion_gate_requires_provenance():
    evidence = PromotionEvidence(*([True] * 8))
    decision = EvidencePromotionGate().evaluate(evidence)
    assert decision.allowed is False
    assert decision.missing == ("provenance",)


def test_promotion_gate_allows_verified_change():
    evidence = PromotionEvidence(*([True] * 8), provenance=("ci://run/456",))
    decision = EvidencePromotionGate().require(evidence)
    assert decision.allowed is True
    assert decision.status == EvidenceStatus.PRODUCTION_VERIFIED


def test_promotion_gate_raises_with_missing_evidence():
    evidence = PromotionEvidence(*([True] * 7 + [False]), provenance=("ci://run/789",))
    try:
        EvidencePromotionGate().require(evidence)
    except PromotionBlocked as exc:
        assert "rollback" in exc.decision.missing
    else:
        raise AssertionError("promotion must be blocked")

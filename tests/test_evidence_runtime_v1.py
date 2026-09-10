from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ois.runtime.evidence import EvidenceLedgerV1, EvidenceRuntimeV1, canonical_digest


def test_ledger_hash_chain_verifies() -> None:
    ledger = EvidenceLedgerV1()
    run_id = uuid4()
    ledger.append(run_id, "ONE", {"value": 1})
    ledger.append(run_id, "TWO", {"value": 2})
    assert ledger.verify() is True
    assert len(ledger.list(run_id)) == 2


def test_observation_cannot_expand_authorization_root() -> None:
    runtime = EvidenceRuntimeV1()
    run_id = uuid4()
    evidence = runtime.ingest(run_id, evidence_type="observation", source_id="test", payload={"x": 1})
    allowed = {"capability": "read", "resource": "fixture"}
    injected = {"capability": "write", "resource": "money"}
    decision = runtime.admissible(
        run_id,
        action=injected,
        evidence_ids=(evidence.evidence_id,),
        policy={"deny": False},
        authorization_root={"allowed_actions": (allowed,)},
    )
    assert decision.allowed is False
    assert "authorization_root_mismatch" in decision.reason_codes


def test_stale_evidence_is_denied() -> None:
    runtime = EvidenceRuntimeV1()
    run_id = uuid4()
    evidence = runtime.ingest(
        run_id,
        evidence_type="observation",
        source_id="test",
        payload={"x": 1},
        observed_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    action = {"capability": "read"}
    decision = runtime.admissible(
        run_id,
        action=action,
        evidence_ids=(evidence.evidence_id,),
        policy={"deny": False},
        authorization_root={"allowed_actions": (action,)},
        max_age_seconds=30,
    )
    assert decision.allowed is False
    assert "stale_evidence" in decision.reason_codes


def test_authorization_is_single_use_and_digest_bound() -> None:
    runtime = EvidenceRuntimeV1()
    run_id = uuid4()
    evidence = runtime.ingest(run_id, evidence_type="observation", source_id="test", payload={"x": 1})
    action = {"capability": "read"}
    policy = {"deny": False}
    decision = runtime.admissible(
        run_id,
        action=action,
        evidence_ids=(evidence.evidence_id,),
        policy=policy,
        authorization_root={"allowed_actions": (action,)},
    )
    auth = runtime.authorize(
        run_id,
        decision=decision,
        action=action,
        evidence_ids=(evidence.evidence_id,),
        policy=policy,
    )
    runtime.execute(
        run_id,
        authorization=auth,
        action=action,
        tool="test",
        executor=lambda _: {"ok": True},
        evidence_ids=(evidence.evidence_id,),
    )
    with pytest.raises(PermissionError, match="unknown_authorization|authorization_replay"):
        runtime.execute(
            run_id,
            authorization=auth,
            action=action,
            tool="test",
            executor=lambda _: {"ok": True},
            evidence_ids=(evidence.evidence_id,),
        )


def test_canonical_digest_is_stable() -> None:
    assert canonical_digest({"b": 2, "a": 1}) == canonical_digest({"a": 1, "b": 2})

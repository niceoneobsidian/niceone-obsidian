from datetime import UTC, datetime, timedelta

import pytest

from ois.domains.social_growth.production_loop import (
    StageEvidence,
    certificate_payload,
    verify_production_loop,
)

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


def _stages(*, live: bool = True) -> tuple[StageEvidence, ...]:
    names = ("source", "evidence", "intelligence", "growth", "outcome", "learning")
    result: list[StageEvidence] = []
    previous = ""
    for index, name in enumerate(names):
        evidence_id = f"{name}-evidence"
        result.append(
            StageEvidence(
                stage=name,
                evidence_id=evidence_id,
                live=live,
                recorded_at=NOW + timedelta(seconds=index),
                source_refs=(previous,) if previous else (),
                artifact_hash=f"sha256-{evidence_id}",
            )
        )
        previous = evidence_id
    return tuple(result)


def test_production_loop_requires_all_live_stages() -> None:
    certificate = verify_production_loop(
        loop_id="loop-1",
        platform="tiktok",
        stages=_stages(),
        certificate_id="cert-1",
        verified_at=NOW,
    )
    assert certificate.production_verified is True
    assert certificate.failures == ()
    assert len(certificate.lineage_hash) == 64


def test_test_evidence_cannot_be_promoted() -> None:
    certificate = verify_production_loop(
        loop_id="loop-1",
        platform="tiktok",
        stages=_stages(live=False),
        certificate_id="cert-1",
        verified_at=NOW,
    )
    assert certificate.production_verified is False
    assert "source evidence is not marked live" in certificate.failures


def test_missing_lineage_reference_fails() -> None:
    stages = list(_stages())
    stages[3] = StageEvidence(
        stage="growth",
        evidence_id="growth-evidence",
        live=True,
        recorded_at=NOW + timedelta(seconds=3),
        source_refs=("wrong-evidence",),
        artifact_hash="sha256-growth-evidence",
    )
    certificate = verify_production_loop(
        loop_id="loop-1",
        platform="tiktok",
        stages=stages,
        certificate_id="cert-1",
        verified_at=NOW,
    )
    assert certificate.production_verified is False
    assert any("growth does not reference prior evidence" in failure for failure in certificate.failures)


def test_missing_stage_fails_closed() -> None:
    certificate = verify_production_loop(
        loop_id="loop-1",
        platform="tiktok",
        stages=_stages()[:-1],
        certificate_id="cert-1",
        verified_at=NOW,
    )
    assert certificate.production_verified is False
    assert "missing required stage: learning" in certificate.failures


def test_certificate_payload_is_serializable() -> None:
    certificate = verify_production_loop(
        loop_id="loop-1",
        platform="tiktok",
        stages=_stages(),
        certificate_id="cert-1",
        verified_at=NOW,
    )
    payload = certificate_payload(certificate)
    assert payload["status"] == "production_verified"
    assert payload["platform"] == "tiktok"
    assert payload["stage_evidence"][0]["stage"] == "source"


def test_live_stage_requires_artifact_hash() -> None:
    with pytest.raises(ValueError):
        StageEvidence(
            stage="source",
            evidence_id="source-1",
            live=True,
            recorded_at=NOW,
        )

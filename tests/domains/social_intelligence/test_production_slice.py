from datetime import UTC, datetime

from ois.domains.social_intelligence.production_slice import normalize_tiktok_videos
from ois.domains.social_intelligence.readiness import build_readiness_manifest
import pytest

from ois.domains.social_intelligence.production_slice import normalize_tiktok_videos
from ois.domains.social_intelligence.readiness import ReadinessCheck, build_readiness_manifest
from ois.infrastructure.source_gateway.evidence import RawEvidence, canonical_hash
from ois.infrastructure.source_gateway.outbox import OutboxEvent


def test_tiktok_normalization_is_deterministic() -> None:
    raw = {
        "data": {
            "videos": [
                {
                    "id": "v1",
                    "create_time": 1779000000,
                    "video_description": "AI agents",
                    "share_url": "https://www.tiktok.com/@example/video/v1",
                    "like_count": 10,
                    "comment_count": 2,
                    "share_count": 3,
                    "view_count": 100,
                }
            ]
        }
    }
    posts = normalize_tiktok_videos(raw)
    assert len(posts) == 1
    assert posts[0].external_id == "v1"
    assert posts[0].metrics.views == 100
    assert posts[0].metrics.shares == 3


def test_readiness_manifest_cannot_claim_production_without_evidence() -> None:
    manifest = build_readiness_manifest()
    assert manifest.production_ready is False
    assert all(check.status != "production_verified" for check in manifest.checks)


def test_scope_and_hash_contracts() -> None:
    payload = {"data": {"videos": [{"id": "v1"}]}}
    evidence = RawEvidence(
        "e1",
        "tenant",
        "workspace",
        "tiktok.display.v2",
        "cursor:initial",
        payload,
        canonical_hash(payload),
        datetime.now(UTC),
        "tiktok-display-v2",
        "tiktok.display.v2",
        "run-1",
    )
    event = OutboxEvent(
        "evt-1",
        "tenant",
        "workspace",
        "source.raw_evidence.created",
        "e1",
        {
            "evidence_id": "e1",
            "source_id": "tiktok.display.v2",
            "payload_hash": evidence.payload_hash,
        },
        datetime.now(UTC),
    )
    assert event.aggregate_id == evidence.evidence_id
    assert evidence.tenant_id == event.tenant_id
    assert canonical_hash(evidence.payload) == evidence.payload_hash


def test_tiktok_normalization_skips_malformed_records() -> None:
    assert normalize_tiktok_videos({}) == ()
    assert normalize_tiktok_videos({"data": {"videos": "not-a-list"}}) == ()
    posts = normalize_tiktok_videos(
        {
            "data": {
                "videos": [
                    {"id": None},
                    {},
                    {"id": "ok", "like_count": "bad", "create_time": "bad"},
                ]
            }
        }
    )
    assert posts[0].external_id == "ok"


def test_production_verified_requires_evidence() -> None:
    with pytest.raises(ValueError):
        ReadinessCheck(
            check_id="SI-01",
            requirement="one real platform",
            status="production_verified",
            evidence=(),
            verified_at=datetime.now(UTC),
        )

"""Production acceptance and lineage verification for the social growth loop.

This module verifies an externally produced evidence chain:
real source -> durable evidence -> intelligence -> growth -> outcome -> learning.
It never fabricates platform evidence or executes external side effects.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

StageName = Literal["source", "evidence", "intelligence", "growth", "outcome", "learning"]
_REQUIRED_ORDER: tuple[StageName, ...] = (
    "source",
    "evidence",
    "intelligence",
    "growth",
    "outcome",
    "learning",
)


@dataclass(frozen=True)
class StageEvidence:
    stage: StageName
    evidence_id: str
    live: bool
    recorded_at: datetime
    source_refs: tuple[str, ...] = ()
    artifact_hash: str = ""

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("stage evidence requires a non-empty evidence_id")
        if self.live and not self.artifact_hash:
            raise ValueError(f"{self.stage} live evidence requires an artifact_hash")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")


@dataclass(frozen=True)
class ProductionLoopCertificate:
    certificate_id: str
    loop_id: str
    platform: str
    generated_at: datetime
    status: Literal["failed", "production_verified"]
    stage_evidence: tuple[StageEvidence, ...]
    lineage_hash: str
    failures: tuple[str, ...] = ()

    @property
    def production_verified(self) -> bool:
        return self.status == "production_verified"


def canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _lineage_hash(stages: Iterable[StageEvidence]) -> str:
    chain: list[str] = []
    previous = ""
    for item in stages:
        material = {
            "stage": item.stage,
            "evidence_id": item.evidence_id,
            "live": item.live,
            "recorded_at": item.recorded_at.isoformat(),
            "source_refs": item.source_refs,
            "artifact_hash": item.artifact_hash,
            "previous": previous,
        }
        current = canonical_hash(material)
        chain.append(current)
        previous = current
    return canonical_hash(chain)


def verify_production_loop(
    *,
    loop_id: str,
    platform: str,
    stages: Iterable[StageEvidence],
    certificate_id: str,
    verified_at: datetime | None = None,
) -> ProductionLoopCertificate:
    """Fail-closed verification of the six-stage production proof chain."""
    evidence = tuple(stages)
    failures: list[str] = []

    if not loop_id.strip():
        failures.append("loop_id is empty")
    if not platform.strip():
        failures.append("platform is empty")
    if verified_at is None:
        failures.append("verified_at is required")
    elif verified_at.tzinfo is None:
        failures.append("verified_at must be timezone-aware")

    by_stage: dict[StageName, StageEvidence] = {}
    for evidence_item in evidence:
        if evidence_item.stage in by_stage:
            failures.append(f"duplicate stage evidence: {evidence_item.stage}")
        by_stage[evidence_item.stage] = evidence_item

    for expected in _REQUIRED_ORDER:
        stage_item = by_stage.get(expected)
        if stage_item is None:
            failures.append(f"missing required stage: {expected}")
            continue
        if not stage_item.live:
            failures.append(f"{expected} evidence is not marked live")
        if not stage_item.artifact_hash:
            failures.append(f"{expected} artifact_hash is empty")

    ordered = [by_stage[s] for s in _REQUIRED_ORDER if s in by_stage]
    # Ordered stages follow the required sequence.
    for previous, current in zip(ordered, ordered[1:], strict=True):
        if previous.evidence_id not in current.source_refs:
            failures.append(
                f"{current.stage} does not reference prior evidence "
                f"{previous.evidence_id}"
            )

    lineage = _lineage_hash(ordered)
    status: Literal["failed", "production_verified"] = (
        "production_verified" if not failures else "failed"
    )
    return ProductionLoopCertificate(
        certificate_id=certificate_id,
        loop_id=loop_id,
        platform=platform,
        generated_at=verified_at or datetime.now(UTC),
        status=status,
        stage_evidence=tuple(ordered),
        lineage_hash=lineage,
        failures=tuple(failures),
    )


def certificate_payload(certificate: ProductionLoopCertificate) -> dict[str, object]:
    payload = asdict(certificate)
    payload["generated_at"] = certificate.generated_at.isoformat()
    payload["stage_evidence"] = [
        {**asdict(item), "recorded_at": item.recorded_at.isoformat()}
        for item in certificate.stage_evidence
    ]
    return payload

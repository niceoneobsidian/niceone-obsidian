"""Fail-closed proof object for the real-source -> outcome -> learning loop."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

Stage = Literal["source", "evidence", "intelligence", "growth", "outcome", "learning"]
STAGES: tuple[Stage, ...] = ("source", "evidence", "intelligence", "growth", "outcome", "learning")


@dataclass(frozen=True)
class LoopArtifact:
    stage: Stage
    artifact_id: str
    tenant_id: str
    occurred_at: datetime
    payload_hash: str
    source_ref: str
    execution_id: str

    @classmethod
    def create(
        cls,
        stage: Stage,
        artifact_id: str,
        tenant_id: str,
        payload: object,
        *,
        source_ref: str,
        execution_id: str,
        occurred_at: datetime | None = None,
    ) -> "LoopArtifact":
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return cls(
            stage,
            artifact_id,
            tenant_id,
            occurred_at or datetime.now(UTC),
            hashlib.sha256(canonical.encode()).hexdigest(),
            source_ref,
            execution_id,
        )


@dataclass(frozen=True)
class ProductionLoopCertificate:
    certificate_id: str
    tenant_id: str
    execution_id: str
    generated_at: datetime
    artifacts: tuple[LoopArtifact, ...]
    lineage_hash: str
    status: Literal["production_verified", "rejected"]

    @property
    def production_verified(self) -> bool:
        return self.status == "production_verified"

    def as_dict(self) -> dict[str, object]:
        return {
            "certificate_id": self.certificate_id,
            "tenant_id": self.tenant_id,
            "execution_id": self.execution_id,
            "generated_at": self.generated_at.isoformat(),
            "status": self.status,
            "lineage_hash": self.lineage_hash,
            "artifacts": [
                {**asdict(a), "occurred_at": a.occurred_at.isoformat()} for a in self.artifacts
            ],
        }


class ProductionLoopProof:
    """Certification is impossible unless every stage has independent evidence."""

    def certify(
        self,
        *,
        certificate_id: str,
        tenant_id: str,
        execution_id: str,
        artifacts: tuple[LoopArtifact, ...],
    ) -> ProductionLoopCertificate:
        if not tenant_id or not execution_id:
            raise ValueError("tenant_id and execution_id are required")
        by_stage: dict[str, list[LoopArtifact]] = {stage: [] for stage in STAGES}
        for artifact in artifacts:
            if artifact.tenant_id != tenant_id or artifact.execution_id != execution_id:
                raise ValueError("loop artifacts must share tenant and execution identity")
            if len(artifact.payload_hash) != 64:
                raise ValueError(f"invalid payload hash for {artifact.artifact_id}")
            by_stage[artifact.stage].append(artifact)

        ordered = tuple(
            artifact
            for stage in STAGES
            for artifact in sorted(by_stage[stage], key=lambda item: item.artifact_id)
        )
        lineage_payload = "|".join(
            f"{a.stage}:{a.artifact_id}:{a.payload_hash}:{a.source_ref}:{a.execution_id}"
            for a in ordered
        )
        lineage_hash = hashlib.sha256(lineage_payload.encode()).hexdigest()
        status: Literal["production_verified", "rejected"] = (
            "production_verified"
            if all(by_stage[stage] for stage in STAGES)
            else "rejected"
        )
        return ProductionLoopCertificate(
            certificate_id,
            tenant_id,
            execution_id,
            datetime.now(UTC),
            ordered,
            lineage_hash,
            status,
        )

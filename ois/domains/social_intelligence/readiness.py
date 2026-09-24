"""Evidence-backed readiness manifest for the focused Social Intelligence slice."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

ReadinessStatus = Literal["designed", "implemented", "tested", "production_verified"]


@dataclass(frozen=True)
class ReadinessCheck:
    check_id: str
    requirement: str
    status: ReadinessStatus
    evidence: tuple[str, ...]
    verified_at: datetime | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.status == "production_verified":
            if not self.evidence:
                raise ValueError(f"{this.check_id} requires evidence before production verification")
            if self.verified_at is None:
                raise ValueError(f"{this.check_id} requires verified_at before production verification")


@dataclass(frozen=True)
class SocialIntelligenceReadinessManifest:
    manifest_version: str
    platform: str
    generated_at: datetime
    checks: tuple[ReadinessCheck, ...]

    @property
    def production_ready(self) -> bool:
        return all(
            check.status == "production_verified"
            and bool(check.evidence)
            and check.verified_at is not None
            for check in self.checks
        )

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["generated_at"] = self.generated_at.isoformat()
        payload["checks"] = [
            {
                **asdict(check),
                "verified_at": check.verified_at.isoformat() if check.verified_at else None,
            }
            for check in self.checks
        ]
        return payload


def build_readiness_manifest(
    *,
    platform: str = "tiktok",
    production_evidence: dict[str, tuple[str, ...]] | None = None,
) -> SocialIntelligenceReadinessManifest:
    evidence = production_evidence or {}
    checks = (
        ReadinessCheck(
            "SI-01",
            "one real platform",
            "implemented" if platform == "tiktok" else "designed",
            evidence.get("SI-01", ()),
            notes="TikTok Display API adapter is present.",
        ),
        ReadinessCheck(
            "SI-02",
            "PostgreSQL-backed raw evidence + outbox",
            "implemented",
            evidence.get("SI-02", ()),
            notes=(
                "Atomic production ledger is implemented; "
                "live DB verification remains evidence-gated."
            ),
        ),
        ReadinessCheck(
            "SI-03",
            "durable publication ledger",
            "implemented",
            evidence.get("SI-03", ()),
            notes="Idempotent publication identity and attempt state are persisted in PostgreSQL.",
        ),
        ReadinessCheck(
            "SI-04",
            "fully verified Social Intelligence slice",
            "tested",
            evidence.get("SI-04", ()),
            notes="Contract tests prove normalization and persistence boundaries; "
            "production verification requires authorized live execution.",
        ),
        ReadinessCheck(
            "SI-05",
            "evidence-backed readiness manifest",
            "tested",
            evidence.get("SI-05", ()),
            notes=(
                "Manifest refuses to report production readiness without "
                "production_verified checks."
            ),
        ),
    )
    return SocialIntelligenceReadinessManifest("1.0.0", platform, datetime.now(UTC), checks)

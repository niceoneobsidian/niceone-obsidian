"""Evidence-gated promotion decisions for OIS runtime changes."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class EvidenceStatus(StrEnum):
    UNKNOWN = "unknown"
    DESIGNED = "designed"
    IMPLEMENTED = "implemented"
    TESTED = "tested"
    INTEGRATED = "integrated"
    DEPLOYED = "deployed"
    ACTIVATED = "activated"
    PRODUCTION_VERIFIED = "production_verified"


@dataclass(frozen=True)
class PromotionEvidence:
    implementation: bool
    tests: bool
    integration: bool
    runtime: bool
    security: bool
    observability: bool
    recovery: bool
    rollback: bool
    provenance: tuple[str, ...] = ()


@dataclass(frozen=True)
class PromotionDecision:
    status: EvidenceStatus
    allowed: bool
    missing: tuple[str, ...]
    reason: str


_REQUIRED = (
    "implementation",
    "tests",
    "integration",
    "runtime",
    "security",
    "observability",
    "recovery",
    "rollback",
)


class EvidencePromotionGate:
    """Prevent production promotion unless independently verifiable evidence exists."""

    def evaluate(self, evidence: PromotionEvidence) -> PromotionDecision:
        missing = tuple(name for name in _REQUIRED if not getattr(evidence, name))
        if missing:
            return PromotionDecision(
                status=EvidenceStatus.INTEGRATED if evidence.integration else EvidenceStatus.TESTED,
                allowed=False,
                missing=missing,
                reason="production promotion blocked: required evidence is missing",
            )

        if not evidence.provenance:
            return PromotionDecision(
                status=EvidenceStatus.INTEGRATED,
                allowed=False,
                missing=("provenance",),
                reason="production promotion blocked: evidence provenance is missing",
            )

        return PromotionDecision(
            status=EvidenceStatus.PRODUCTION_VERIFIED,
            allowed=True,
            missing=(),
            reason="all production promotion evidence requirements are satisfied",
        )

    def require(self, evidence: PromotionEvidence) -> PromotionDecision:
        decision = self.evaluate(evidence)
        if not decision.allowed:
            raise PromotionBlocked(decision)
        return decision


class PromotionBlocked(RuntimeError):
    """Raised when a production activation lacks required evidence."""

    def __init__(self, decision: PromotionDecision) -> None:
        self.decision = decision
        super().__init__(f"{decision.reason}: {', '.join(decision.missing)}")


def verified_from(checks: Iterable[bool], provenance: Iterable[str]) -> PromotionEvidence:
    """Build evidence from independently collected boolean verification checks."""
    values = tuple(checks)
    if len(values) != len(_REQUIRED):
        raise ValueError(f"expected {len(_REQUIRED)} checks, got {len(values)}")
    return PromotionEvidence(*values, provenance=tuple(provenance))  # type: ignore

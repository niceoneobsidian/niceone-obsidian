"""Explicit provider conformance metadata contracts.

Runtime adapter behavior and governance evidence are separate concerns. This
module provides the typed bridge between them: a registered provider may
declare explicit evidence-backed conformance claims without making the
conformance auditor infer claims from generic implementation details.

Claims are intentionally source-ID scoped and immutable. Live and production
verification still require runtime/CI evidence; metadata alone never creates
those proofs.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

CONFORMANCE_METADATA_COLUMNS: Final[tuple[str, ...]] = (
    "ADAPTER",
    "REGISTRATION",
    "CAPABILITY",
    "TOOL",
    "AUTH",
    "CREDENTIAL",
    "SCOPES",
    "POLICY",
    "RATE LIMIT",
    "RETRY",
    "TIMEOUT",
    "IDEMPOTENCY",
    "EVENTS",
    "PROVENANCE",
    "EVIDENCE",
    "STRUCTURAL TEST",
    "CONTRACT TEST",
    "LIVE TEST",
    "E2E TEST",
    "NEGATIVE TEST",
    "CI GATE",
    "PRODUCTION VERIFICATION",
)

CONFORMANCE_METADATA_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "IMPLEMENTED",
        "TESTED",
        "INTEGRATED",
        "LIVE VERIFIED",
        "E2E VERIFIED",
        "PRODUCTION VERIFIED",
        "N/A",
        "MISSING",
        "UNKNOWN",
    }
)


@dataclass(frozen=True)
class ConformanceEvidence:
    """One explicit, source-scoped conformance claim."""

    status: str
    evidence: tuple[str, ...] = ()
    note: str | None = None

    def __post_init__(self) -> None:
        if self.status not in CONFORMANCE_METADATA_STATUSES:
            raise ValueError(f"unknown conformance status: {self.status}")
        if not self.evidence and self.status not in {"UNKNOWN", "N/A"}:
            raise ValueError("non-unknown conformance claims require evidence")
        if self.status in {"LIVE VERIFIED", "E2E VERIFIED", "PRODUCTION VERIFIED"}:
            raise ValueError(
                "runtime verification statuses require runtime/CI evidence, not provider metadata"
            )


@dataclass(frozen=True)
class ProviderConformanceMetadata:
    """Evidence contract attached to one canonical source adapter."""

    source_id: str
    claims: Mapping[str, ConformanceEvidence]

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id is required")
        unknown = set(self.claims) - set(CONFORMANCE_METADATA_COLUMNS)
        if unknown:
            raise ValueError(f"unknown conformance metadata columns: {sorted(unknown)}")
        object.__setattr__(self, "claims", MappingProxyType(dict(self.claims)))

    def claim(self, column: str) -> ConformanceEvidence | None:
        return self.claims.get(column)

    def columns(self) -> tuple[str, ...]:
        return tuple(self.claims)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "claims": {
                column: {
                    "status": claim.status,
                    "evidence": list(claim.evidence),
                    "note": claim.note,
                }
                for column, claim in self.claims.items()
            },
        }

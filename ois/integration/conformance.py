"""Canonical repository-wide integration conformance framework.

The framework discovers registered source adapters from the existing
SourceAdapterRegistry and produces one stable 23-column conformance matrix.
Unknown dimensions remain UNKNOWN until explicit evidence is supplied.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Callable, Iterable, Mapping

from ois.infrastructure.source_adapters.base import SourceAdapter, SourceAdapterRegistry
from ois.infrastructure.source_gateway.contracts import SourceSpec


class ConformanceStatus(StrEnum):
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    INTEGRATED = "INTEGRATED"
    LIVE_VERIFIED = "LIVE VERIFIED"
    E2E_VERIFIED = "E2E VERIFIED"
    PRODUCTION_VERIFIED = "PRODUCTION VERIFIED"
    NOT_APPLICABLE = "N/A"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"

CONFORMANCE_COLUMNS: tuple[str, ...] = (
    "PROVIDER",
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

@dataclass(frozen=True)
class ConformanceCell:
    status: ConformanceStatus
    evidence: tuple[str, ...] = ()
    note: str | None = None

@dataclass(frozen=True)
class IntegrationConformanceRecord:
    provider_id: str
    source_id: str
    cells: Mapping[str, ConformanceCell]

    def __post_init__(self) -> None:
        if tuple(self.cells) != CONFORMANCE_COLUMNS:
            raise ValueError("record must contain exactly the canonical 23 columns in order")

    def row(self) -> dict[str, str]:
        return {column: self.cells[column].status.value for column in CONFORMANCE_COLUMNS}

    def evidence_row(self) -> dict[str, dict[str, Any]]:
        return {column: asdict(self.cells[column]) for column in CONFORMANCE_COLUMNS}

@dataclass(frozen=True)
class ConformanceReport:
    records: tuple[IntegrationConformanceRecord, ...]
    generated_by: str = "ois.integration.conformance.v1"

    @property
    def columns(self) -> tuple[str, ...]:
        return CONFORMANCE_COLUMNS

    @property
    def matrix(self) -> tuple[dict[str, str], ...]:
        return tuple(record.row() for record in self.records)

    @property
    def failed(self) -> tuple[IntegrationConformanceRecord, ...]:
        blocking = {ConformanceStatus.MISSING, ConformanceStatus.UNKNOWN}
        return tuple(
            record
            for record in self.records
            if any(cell.status in blocking for cell in record.cells.values())
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "generated_by": self.generated_by,
            "columns": list(self.columns),
            "matrix": list(self.matrix),
            "evidence": {
                record.source_id: record.evidence_row()
                for record in self.records
            },
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False)

MetadataVerifier = Callable[
    [str, SourceAdapter, SourceSpec],
    Mapping[
        str,
        ConformanceCell | ConformanceStatus | str | Mapping[str, Any],
    ],
]

class IntegrationConformance:
    """Canonical registry-driven conformance auditor."""

    def __init__(
        self,
        registry: SourceAdapterRegistry,
        *,
        verifier: MetadataVerifier | None = None,
    ) -> None:
        self._registry = registry
        self._verifier = verifier

    def discover(self) -> tuple[str, ...]:
        return self._registry.list()

    def audit(self) -> ConformanceReport:
        records = tuple(self._audit_one(source_id) for source_id in self.discover())
        return ConformanceReport(records)

    def _audit_one(self, source_id: str) -> IntegrationConformanceRecord:
        adapter = self._registry.get(source_id)
        spec = self._registry.spec(source_id)
        cells = self._base_cells(source_id, adapter, spec)
        if self._verifier is not None:
            for column, value in self._verifier(source_id, adapter, spec).items():
                if column not in CONFORMANCE_COLUMNS:
                    raise ValueError(f"unknown conformance column: {column}")
                cells[column] = self._coerce_cell(value)
        cells["PROVIDER"] = ConformanceCell(
            ConformanceStatus.IMPLEMENTED,
            (f"SourceSpec.provider={spec.provider}",),
        )
        return IntegrationConformanceRecord(spec.provider, source_id, cells)

    @staticmethod
    def _base_cells(
        source_id: str,
        adapter: SourceAdapter,
        spec: SourceSpec,
    ) -> dict[str, ConformanceCell]:
        has_ingest = callable(getattr(adapter, "ingest", None))
        cells = {
            column: ConformanceCell(ConformanceStatus.UNKNOWN)
            for column in CONFORMANCE_COLUMNS
        }
        cells["ADAPTER"] = ConformanceCell(
            ConformanceStatus.IMPLEMENTED if has_ingest else ConformanceStatus.MISSING,
            ("SourceAdapter.ingest" if has_ingest else "adapter.ingest missing",),
        )
        cells["REGISTRATION"] = ConformanceCell(
            ConformanceStatus.IMPLEMENTED, ("SourceAdapterRegistry",)
        )
        cells["CAPABILITY"] = ConformanceCell(
            ConformanceStatus.IMPLEMENTED if spec.capabilities else ConformanceStatus.UNKNOWN,
            (f"SourceSpec.capabilities={spec.capabilities!r}",),
        )
        cells["PROVENANCE"] = ConformanceCell(
            ConformanceStatus.IMPLEMENTED, ("SourceProvenance gateway contract",)
        )
        cells["EVIDENCE"] = ConformanceCell(
            ConformanceStatus.IMPLEMENTED,
            ("RawEvidence/source ledger gateway boundary",),
        )
        for column, note in {
            "TOOL": "Tool Registry mapping requires explicit evidence",
            "AUTH": "Authentication binding requires explicit evidence",
            "CREDENTIAL": "Credential binding requires explicit evidence",
            "SCOPES": "Credential scopes require explicit evidence",
            "POLICY": "Policy authorization requires explicit evidence",
            "RATE LIMIT": "Provider-specific rate-limit conformance requires evidence",
            "RETRY": "Provider-specific retry conformance requires evidence",
            "TIMEOUT": "Provider-specific timeout behavior requires evidence",
            "IDEMPOTENCY": "Provider-specific idempotency behavior requires evidence",
            "EVENTS": "Provider event normalization requires evidence",
            "STRUCTURAL TEST": "Universal structural test evidence required",
            "CONTRACT TEST": "Provider contract evidence required",
            "LIVE TEST": "Opt-in live evidence required",
            "E2E TEST": "Governed end-to-end evidence required",
            "NEGATIVE TEST": "Security/recovery negative evidence required",
            "CI GATE": "CI promotion mapping requires evidence",
            "PRODUCTION VERIFICATION": "Production proof must be explicit and fail-closed",
        }.items():
            cells[column] = ConformanceCell(ConformanceStatus.UNKNOWN, (note,))
        return cells

    @staticmethod
    def _coerce_cell(
        value: ConformanceCell
        | ConformanceStatus
        | str
        | Mapping[str, Any],
    ) -> ConformanceCell:
        if isinstance(value, ConformanceCell):
            return value
        if isinstance(value, ConformanceStatus):
            return ConformanceCell(value)
        if isinstance(value, str):
            return ConformanceCell(ConformanceStatus(value))
        return ConformanceCell(
            ConformanceStatus(str(value["status"])),
            tuple(map(str, value.get("evidence", ()))),
            value.get("note"),
        )

def audit_registered_integrations(
    registry: SourceAdapterRegistry,
    *,
    verifier: MetadataVerifier | None = None,
) -> ConformanceReport:
    return IntegrationConformance(registry, verifier=verifier).audit()

def rows(report: ConformanceReport) -> Iterable[dict[str, str]]:
    return report.matrix
"""Evidence-backed cross-source fusion and research contracts."""

from __future__ import annotations

from dataclasses import dataclass

from .evidence import EvidenceRelation, IntelligenceClaim, SQLiteEvidenceStore


@dataclass(frozen=True)
class CrossSourceFinding:
    statement: str
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    confidence: float
    contradiction: bool = False


class CrossSourceResearch:
    def __init__(self, evidence: SQLiteEvidenceStore) -> None:
        self._evidence = evidence

    def build_finding(
        self,
        *,
        claim_id: str,
        statement: str,
        entity_id: str,
        evidence_ids: tuple[str, ...],
        source_ids: tuple[str, ...],
        confidence: float,
    ) -> CrossSourceFinding:
        if not evidence_ids:
            raise ValueError("cross-source finding requires evidence")
        self._evidence.add_claim(
            IntelligenceClaim(
                claim_id,
                statement,
                evidence_ids,
                (entity_id,),
                confidence,
            )
        )
        for index, source in enumerate(source_ids):
            self._evidence.add_relation(
                EvidenceRelation(
                    f"{claim_id}:source:{index}",
                    entity_id,
                    "supported_by",
                    source,
                    evidence_ids,
                    confidence,
                )
            )
        return CrossSourceFinding(statement, source_ids, evidence_ids, confidence)

    def research_brief(
        self, *, query: str, findings: tuple[CrossSourceFinding, ...]
    ) -> dict[str, object]:
        if not findings:
            raise ValueError("research brief requires findings")
        return {
            "query": query,
            "findings": [finding.statement for finding in findings],
            "evidence_ids": tuple(
                evidence_id for finding in findings for evidence_id in finding.evidence_ids
            ),
            "source_ids": tuple(
                sorted({source_id for finding in findings for source_id in finding.source_ids})
            ),
            "confidence": sum(finding.confidence for finding in findings) / len(findings),
        }

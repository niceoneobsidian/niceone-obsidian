"""Evidence-backed cross-source fusion and research contracts."""
from __future__ import annotations
from dataclasses import dataclass
from .evidence import IntelligenceClaim, EvidenceRelation, SQLiteEvidenceStore

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
    def build_finding(self, *, claim_id: str, statement: str, entity_id: str,
                      evidence_ids: tuple[str, ...], source_ids: tuple[str, ...],
                      confidence: float) -> CrossSourceFinding:
        if not evidence_ids: raise ValueError("cross-source finding requires evidence")
        self._evidence.add_claim(IntelligenceClaim(claim_id, statement, evidence_ids, (entity_id,), confidence))
        for index, source_id in enumerate(source_ids):
            self._evidence.add_relation(EvidenceRelation(
                f"{claim_id}:source:{index}", entity_id, "supported_by", source_id, evidence_ids, confidence))
        return CrossSourceFinding(statement, source_ids, evidence_ids, confidence)
    def research_brief(self, *, query: str, findings: tuple[CrossSourceFinding, ...]) -> dict:
        if not findings: raise ValueError("research brief requires findings")
        evidence=tuple(e for f in findings for e in f.evidence_ids)
        sources=tuple(sorted({s for f in findings for s in f.source_ids}))
        confidence=sum(f.confidence for f in findings)/len(findings)
        return {"query":query,"findings":[f.statement for f in findings],
                "evidence_ids":evidence,"source_ids":sources,"confidence":confidence}

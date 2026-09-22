"""Cross-source research over provenance-backed graph evidence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ois.domains.social_growth.schemas import Evidence, SocialResearchBrief

from .graph import EvidenceGraph, deterministic_entity_id


@dataclass(frozen=True)
class CrossSourceFinding:
    statement: str
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    confidence: float
    corroborated: bool


class CrossSourceResearch:
    def __init__(self, graph: EvidenceGraph) -> None:
        self._graph = graph

    def corroboration(
        self, *, tenant_id: str, workspace_id: str, entity_id: str
    ) -> tuple[CrossSourceFinding, ...]:
        entity = self._graph.get_node(entity_id)
        if entity is None:
            return ()
        if (entity.tenant_id, entity.workspace_id) != (
            tenant_id,
            workspace_id,
        ):
            raise PermissionError("cross-scope research access")

        evidence_ids: list[str] = []
        sources: set[str] = set()
        for evidence in self._graph.nodes(kind="evidence", limit=10000):
            if (evidence.tenant_id, evidence.workspace_id) != (
                tenant_id,
                workspace_id,
            ):
                continue
            for edge in self._graph.neighbors(
                evidence.node_id, kinds={"supports", "mentions"}
            ):
                if edge.to_id != entity_id:
                    continue
                if evidence.source_id:
                    evidence_ids.append(evidence.node_id)
                    sources.add(evidence.source_id)

        if not evidence_ids:
            return ()

        confidence = min(1.0, 0.5 + 0.15 * max(0, len(sources) - 1))
        name = entity.payload.get("canonical_name", entity_id)
        return (
            CrossSourceFinding(
                f"{name} is supported by evidence from {len(sources)} source(s).",
                tuple(sorted(sources)),
                tuple(evidence_ids),
                confidence,
                len(sources) >= 2,
            ),
        )

    def build_brief(
        self,
        *,
        query: str,
        tenant_id: str,
        workspace_id: str,
        entity_names: Iterable[str],
    ) -> SocialResearchBrief:
        names = list(entity_names)
        findings: list[str] = []
        evidence: list[Evidence] = []
        confidences: list[float] = []

        for name in names:
            entity = self._graph.get_node(
                deterministic_entity_id("topic", name)
            )
            if entity is None:
                continue
            for finding in self.corroboration(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                entity_id=entity.node_id,
            ):
                findings.append(finding.statement)
                confidences.append(finding.confidence)
                for evidence_id in finding.evidence_ids:
                    node = self._graph.get_node(evidence_id)
                    if node:
                        evidence.append(
                            Evidence(
                                source_id=node.source_id or "unknown",
                                uri=node.payload.get("uri"),
                                excerpt=node.payload.get("excerpt")
                                or node.payload.get("text"),
                                observed_at=node.observed_at,
                                confidence=finding.confidence,
                            )
                        )

        confidence = (
            sum(confidences) / len(confidences) if confidences else 0.0
        )
        return SocialResearchBrief(
            query=query,
            sources=evidence,
            entities=names,
            findings=findings,
            confidence=confidence,
        )

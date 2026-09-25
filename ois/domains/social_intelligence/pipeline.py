"""G1 Phase 3/4 orchestration: outbox -> graph -> cross-source research."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ois.domains.social_growth.schemas import SocialResearchBrief
from ois.infrastructure.source_gateway.outbox import OutboxStore

from .graph import EvidenceGraph
from .graph_ingestion import EvidenceGraphProjector, EvidenceReader
from .research import CrossSourceResearch


@dataclass(frozen=True)
class ProjectionReport:
    consumed: int
    projected: int
    event_ids: tuple[str, ...]


class G1ResearchPipeline:
    def __init__(
        self,
        *,
        outbox: OutboxStore,
        graph: EvidenceGraph,
        evidence_reader: EvidenceReader | None = None,
    ) -> None:
        self._outbox = outbox
        self._projector = EvidenceGraphProjector(graph, evidence_reader)
        self._research = CrossSourceResearch(graph)

    def project_pending(self, *, limit: int = 100) -> ProjectionReport:
        events = self._outbox.pending(limit=limit)
        projected = 0
        event_ids: list[str] = []
        for event in events:
            created = self._projector.project(event)
            projected += len(created)
            event_ids.append(event.event_id)
            self._outbox.mark_published(event.event_id)
        return ProjectionReport(len(events), projected, tuple(event_ids))

    def research(
        self,
        *,
        query: str,
        tenant_id: str,
        workspace_id: str,
        entity_names: Iterable[str],
    ) -> SocialResearchBrief:
        return self._research.build_brief(
            query=query,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            entity_names=entity_names,
        )

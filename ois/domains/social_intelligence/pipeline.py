"""G1 Phase 3/4 orchestration: outbox -> graph -> cross-source research."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from ois.infrastructure.source_gateway.outbox import OutboxEvent, OutboxStore
from .graph import EvidenceGraph
from .graph_ingestion import EvidenceGraphProjector
from .research import CrossSourceResearch

@dataclass(frozen=True)
class ProjectionReport:
    consumed:int
    projected:int
    event_ids:tuple[str,...]

class G1ResearchPipeline:
    def __init__(self,*,outbox:OutboxStore,graph:EvidenceGraph)->None:
        self._outbox=outbox
        self._projector=EvidenceGraphProjector(graph)
        self._research=CrossSourceResearch(graph)

    def project_pending(self,*,limit:int=100)->ProjectionReport:
        events=self._outbox.pending(limit=limit)
        projected=0; ids=[]
        for event in events:
            created=self._projector.project(event)
            projected += len(created)
            ids.append(event.event_id)
            self._outbox.mark_published(event.event_id)
        return ProjectionReport(len(events),projected,tuple(ids))

    def research(self,*,query:str,tenant_id:str,workspace_id:str,entity_names:Iterable[str]):
        return self._research.build_brief(query=query,tenant_id=tenant_id,workspace_id=workspace_id,entity_names=entity_names)

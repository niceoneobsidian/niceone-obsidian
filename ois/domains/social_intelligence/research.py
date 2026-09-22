"""Cross-source research over provenance-backed graph evidence."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from ois.domains.social_growth.schemas import Evidence, SocialResearchBrief
from .graph import EvidenceGraph, GraphNode, deterministic_entity_id

@dataclass(frozen=True)
class CrossSourceFinding:
    statement:str
    source_ids:tuple[str,...]
    evidence_ids:tuple[str,...]
    confidence:float
    corroborated:bool

class CrossSourceResearch:
    def __init__(self,graph:EvidenceGraph)->None:self._graph=graph

    def corroboration(self,*,tenant_id:str,workspace_id:str,entity_id:str)->tuple[CrossSourceFinding,...]:
        entity=self._graph.get_node(entity_id)
        if entity is None:return ()
        if (entity.tenant_id,entity.workspace_id)!=(tenant_id,workspace_id):raise PermissionError("cross-scope research access")
        evidence_ids=[]; sources=set()
        for edge in self._graph.neighbors(entity_id,kinds={"supports","mentions"}):
            node=self._graph.get_node(edge.from_id if edge.to_id==entity_id else edge.to_id)
            if node and node.kind=="evidence" and node.source_id:
                evidence_ids.append(node.node_id); sources.add(node.source_id)
        if not evidence_ids:return ()
        confidence=min(1.0,0.5+0.15*max(0,len(sources)-1))
        return (CrossSourceFinding(f'{entity.payload.get("canonical_name",entity_id)} is supported by evidence from {len(sources)} source(s).',tuple(sorted(sources)),tuple(evidence_ids),confidence,len(sources)>=2),)

    def build_brief(self,*,query:str,tenant_id:str,workspace_id:str,entity_names:Iterable[str])->SocialResearchBrief:
        names=list(entity_names); findings=[]; evidence=[]; conf=[]
        for name in names:
            entity=self._graph.get_node(deterministic_entity_id("topic",name))
            if entity is None:continue
            for f in self.corroboration(tenant_id=tenant_id,workspace_id=workspace_id,entity_id=entity.node_id):
                findings.append(f.statement); conf.append(f.confidence)
                for eid in f.evidence_ids:
                    n=self._graph.get_node(eid)
                    if n:evidence.append(Evidence(source_id=n.source_id or "unknown",uri=n.payload.get("uri"),excerpt=n.payload.get("excerpt") or n.payload.get("text"),observed_at=n.observed_at,confidence=f.confidence))
        return SocialResearchBrief(query=query,sources=evidence,entities=names,findings=findings,confidence=sum(conf)/len(conf) if conf else 0.0)

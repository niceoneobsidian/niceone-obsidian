"""Project source outbox evidence into the G1 provenance graph."""
from __future__ import annotations
from datetime import UTC, datetime
from typing import Any
from ois.infrastructure.source_gateway.outbox import OutboxEvent
from .graph import EvidenceGraph, GraphEdge, GraphNode, canonical_hash, deterministic_entity_id

class EvidenceGraphProjector:
    def __init__(self, graph: EvidenceGraph) -> None: self._graph=graph
    def project(self,event:OutboxEvent)->tuple[str,...]:
        if event.event_type!="source.raw_evidence.created": return ()
        p=event.payload; raw=p.get("payload",{})
        observed=_time(p.get("collected_at"))
        node=GraphNode(event.aggregate_id,"evidence",event.tenant_id,event.workspace_id,p.get("source_id"),raw,p.get("payload_hash") or canonical_hash(raw),observed)
        self._graph.upsert_node(node); created=[node.node_id]
        for topic in _topics(raw):
            eid=deterministic_entity_id("topic",topic)
            entity=GraphNode(eid,"entity",event.tenant_id,event.workspace_id,None,{"entity_type":"topic","canonical_name":topic,"attributes":{}},canonical_hash({"entity_type":"topic","canonical_name":topic}),datetime.now(UTC))
            self._graph.upsert_node(entity)
            edge=GraphEdge(f"mentions:{node.node_id}:{eid}",event.tenant_id,event.workspace_id,node.node_id,eid,"mentions",0.75,(node.node_id,),datetime.now(UTC))
            if self._graph.add_edge(edge): created.append(edge.edge_id)
        return tuple(created)

def _time(value:Any)->datetime:
    if isinstance(value,str):
        try:return datetime.fromisoformat(value)
        except ValueError:pass
    return datetime.now(UTC)

def _topics(payload:dict[str,Any])->tuple[str,...]:
    out=set()
    for k in ("title","video_description","text"):
        v=payload.get(k)
        if isinstance(v,str) and v.strip(): out.add(v.strip())
    v=payload.get("topics")
    if isinstance(v,list): out.update(str(x).strip() for x in v if str(x).strip())
    return tuple(sorted(out))

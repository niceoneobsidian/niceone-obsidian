from datetime import UTC, datetime
from ois.domains.social_intelligence.graph import GraphEdge, GraphNode, SQLiteEvidenceGraph, canonical_hash, deterministic_entity_id
from ois.domains.social_intelligence.graph_ingestion import EvidenceGraphProjector
from ois.domains.social_intelligence.research import CrossSourceResearch
from ois.infrastructure.source_gateway.outbox import OutboxEvent

def ev(eid,source,text):
    p={"text":text,"topics":["AI agents"]}
    return GraphNode(eid,"evidence","t","w",source,p,canonical_hash(p),datetime.now(UTC))

def test_graph_rejects_cross_scope_edges():
    g=SQLiteEvidenceGraph(); g.upsert_node(ev("e1","tiktok","AI agents"))
    g.upsert_node(GraphNode("e2","entity","other","w",None,{"canonical_name":"AI agents"},"h",datetime.now(UTC)))
    try:g.add_edge(GraphEdge("x","t","w","e1","e2","mentions",.9,(),datetime.now(UTC)))
    except PermissionError:return
    raise AssertionError("expected cross-scope graph edge rejection")

def test_outbox_projects_evidence_and_entity():
    g=SQLiteEvidenceGraph(); p=EvidenceGraphProjector(g); payload={"topics":["AI agents"]}
    event=OutboxEvent("evt","t","w","source.raw_evidence.created","e1",{"source_id":"tiktok.display.v2","payload":payload,"payload_hash":canonical_hash(payload),"collected_at":datetime.now(UTC).isoformat()},datetime.now(UTC))
    assert "e1" in p.project(event)
    assert g.get_node(deterministic_entity_id("topic","AI agents")) is not None

def test_cross_source_research_corroborates():
    g=SQLiteEvidenceGraph(); eid=deterministic_entity_id("topic","AI agents")
    g.upsert_node(GraphNode(eid,"entity","t","w",None,{"entity_type":"topic","canonical_name":"AI agents"},"h",datetime.now(UTC)))
    for i,source in enumerate(("tiktok.display.v2","youtube")):
        n=ev("e"+str(i),source,"AI agents"); g.upsert_node(n)
        g.add_edge(GraphEdge("edge"+str(i),"t","w",n.node_id,eid,"supports",.9,(n.node_id,),datetime.now(UTC)))
    f=CrossSourceResearch(g).corroboration(tenant_id="t",workspace_id="w",entity_id=eid)[0]
    assert f.corroborated and set(f.source_ids)=={"tiktok.display.v2","youtube"}

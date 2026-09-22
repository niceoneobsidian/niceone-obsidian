"""Evidence/entity graph for provenance-first G1 intelligence."""
from __future__ import annotations
import hashlib, json, sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

NodeKind = Literal["evidence", "event", "entity", "claim"]
EdgeKind = Literal["supports", "derived_from", "mentions", "same_as", "contradicts"]

@dataclass(frozen=True)
class GraphNode:
    node_id: str
    kind: NodeKind
    tenant_id: str
    workspace_id: str
    source_id: str | None
    payload: dict[str, Any]
    content_hash: str
    observed_at: datetime

@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    tenant_id: str
    workspace_id: str
    from_id: str
    to_id: str
    kind: EdgeKind
    confidence: float
    provenance_ids: tuple[str, ...] = ()
    created_at: datetime = datetime.min.replace(tzinfo=UTC)

def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

class EvidenceGraph(Protocol):
    def upsert_node(self, node: GraphNode) -> bool: ...
    def add_edge(self, edge: GraphEdge) -> bool: ...
    def get_node(self, node_id: str) -> GraphNode | None: ...
    def neighbors(self, node_id: str, *, kinds: set[EdgeKind] | None = None) -> tuple[GraphEdge, ...]: ...
    def nodes(self, *, kind: NodeKind | None = None, limit: int = 1000) -> tuple[GraphNode, ...]: ...

class SQLiteEvidenceGraph:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS graph_nodes (
          node_id TEXT PRIMARY KEY, kind TEXT NOT NULL, tenant_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL, source_id TEXT, payload TEXT NOT NULL,
          content_hash TEXT NOT NULL, observed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS graph_edges (
          edge_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
          from_id TEXT NOT NULL, to_id TEXT NOT NULL, kind TEXT NOT NULL,
          confidence REAL NOT NULL, provenance_ids TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(from_id) REFERENCES graph_nodes(node_id),
          FOREIGN KEY(to_id) REFERENCES graph_nodes(node_id));
        """)
        self._db.commit()

    def upsert_node(self, node: GraphNode) -> bool:
        existing = self.get_node(node.node_id)
        if existing and (existing.tenant_id, existing.workspace_id) != (node.tenant_id, node.workspace_id):
            raise PermissionError("cross-tenant/workspace node collision")
        self._db.execute("""INSERT INTO graph_nodes VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(node_id) DO UPDATE SET payload=excluded.payload,
        content_hash=excluded.content_hash, observed_at=excluded.observed_at, source_id=excluded.source_id""",
        (node.node_id,node.kind,node.tenant_id,node.workspace_id,node.source_id,json.dumps(node.payload,sort_keys=True,default=str),node.content_hash,node.observed_at.isoformat()))
        self._db.commit()
        return existing is None

    def add_edge(self, edge: GraphEdge) -> bool:
        if not 0 <= edge.confidence <= 1: raise ValueError("edge confidence must be between 0 and 1")
        left, right = self.get_node(edge.from_id), self.get_node(edge.to_id)
        if left is None or right is None: raise KeyError("both graph edge endpoints must exist")
        if any((n.tenant_id,n.workspace_id)!=(edge.tenant_id,edge.workspace_id) for n in (left,right)):
            raise PermissionError("cross-scope graph edge")
        try:
            self._db.execute("INSERT INTO graph_edges VALUES (?,?,?,?,?,?,?,?,?)",
                (edge.edge_id,edge.tenant_id,edge.workspace_id,edge.from_id,edge.to_id,edge.kind,edge.confidence,json.dumps(edge.provenance_ids),edge.created_at.isoformat()))
            self._db.commit(); return True
        except sqlite3.IntegrityError:
            self._db.rollback(); return False

    def get_node(self, node_id: str) -> GraphNode | None:
        r=self._db.execute("SELECT * FROM graph_nodes WHERE node_id=?",(node_id,)).fetchone()
        if r is None: return None
        return GraphNode(r["node_id"],r["kind"],r["tenant_id"],r["workspace_id"],r["source_id"],json.loads(r["payload"]),r["content_hash"],datetime.fromisoformat(r["observed_at"]))

    def neighbors(self,node_id: str,*,kinds: set[EdgeKind]|None=None)->tuple[GraphEdge,...]:
        if kinds:
            ph=",".join("?" for _ in kinds); rows=self._db.execute(f"SELECT * FROM graph_edges WHERE from_id=? AND kind IN ({ph})",(node_id,*sorted(kinds))).fetchall()
        else: rows=self._db.execute("SELECT * FROM graph_edges WHERE from_id=?",(node_id,)).fetchall()
        return tuple(GraphEdge(r["edge_id"],r["tenant_id"],r["workspace_id"],r["from_id"],r["to_id"],r["kind"],r["confidence"],tuple(json.loads(r["provenance_ids"])),datetime.fromisoformat(r["created_at"])) for r in rows)

    def nodes(self,*,kind:NodeKind|None=None,limit:int=1000)->tuple[GraphNode,...]:
        q="SELECT * FROM graph_nodes"; p=()
        if kind: q+=" WHERE kind=?"; p=(kind,)
        rows=self._db.execute(q+" ORDER BY observed_at DESC LIMIT ?",(*p,limit)).fetchall()
        return tuple(GraphNode(r["node_id"],r["kind"],r["tenant_id"],r["workspace_id"],r["source_id"],json.loads(r["payload"]),r["content_hash"],datetime.fromisoformat(r["observed_at"])) for r in rows)

def deterministic_entity_id(entity_type: str, canonical_name: str) -> str:
    return "entity:"+hashlib.sha256(f"{entity_type}:{canonical_name.strip().casefold()}".encode()).hexdigest()[:32]

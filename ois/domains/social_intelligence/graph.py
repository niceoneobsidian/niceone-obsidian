"""Evidence/entity graph for provenance-first G1 intelligence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
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
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class EvidenceGraph(Protocol):
    def upsert_node(self, node: GraphNode) -> bool: ...
    def add_edge(self, edge: GraphEdge) -> bool: ...
    def get_node(self, node_id: str) -> GraphNode | None: ...
    def neighbors(
        self, node_id: str, *, kinds: set[EdgeKind] | None = None
    ) -> tuple[GraphEdge, ...]: ...
    def nodes(
        self, *, kind: NodeKind | None = None, limit: int = 1000
    ) -> tuple[GraphNode, ...]: ...


class SQLiteEvidenceGraph:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS graph_nodes (
              node_id TEXT PRIMARY KEY, kind TEXT NOT NULL, tenant_id TEXT NOT NULL,
              workspace_id TEXT NOT NULL, source_id TEXT, payload TEXT NOT NULL,
              content_hash TEXT NOT NULL, observed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS graph_edges (
              edge_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
              workspace_id TEXT NOT NULL, from_id TEXT NOT NULL, to_id TEXT NOT NULL,
              kind TEXT NOT NULL, confidence REAL NOT NULL,
              provenance_ids TEXT NOT NULL, created_at TEXT NOT NULL,
              FOREIGN KEY(from_id) REFERENCES graph_nodes(node_id),
              FOREIGN KEY(to_id) REFERENCES graph_nodes(node_id)
            );
            """
        )
        self._db.commit()

    def upsert_node(self, node: GraphNode) -> bool:
        existing = self.get_node(node.node_id)
        if existing and (
            existing.tenant_id,
            existing.workspace_id,
        ) != (node.tenant_id, node.workspace_id):
            raise PermissionError("cross-tenant/workspace node collision")
        self._db.execute(
            """
            INSERT INTO graph_nodes
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(node_id) DO UPDATE SET payload=excluded.payload,
            content_hash=excluded.content_hash, observed_at=excluded.observed_at,
            source_id=excluded.source_id
            """,
            (
                node.node_id,
                node.kind,
                node.tenant_id,
                node.workspace_id,
                node.source_id,
                json.dumps(node.payload, sort_keys=True, default=str),
                node.content_hash,
                node.observed_at.isoformat(),
            ),
        )
        self._db.commit()
        return existing is None

    def add_edge(self, edge: GraphEdge) -> bool:
        if not 0 <= edge.confidence <= 1:
            raise ValueError("edge confidence must be between 0 and 1")
        left = self.get_node(edge.from_id)
        right = self.get_node(edge.to_id)
        if left is None or right is None:
            raise KeyError("both graph edge endpoints must exist")
        if any(
            (node.tenant_id, node.workspace_id) != (edge.tenant_id, edge.workspace_id)
            for node in (left, right)
        ):
            raise PermissionError("cross-scope graph edge")
        try:
            self._db.execute(
                "INSERT INTO graph_edges VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    edge.edge_id,
                    edge.tenant_id,
                    edge.workspace_id,
                    edge.from_id,
                    edge.to_id,
                    edge.kind,
                    edge.confidence,
                    json.dumps(edge.provenance_ids),
                    edge.created_at.isoformat(),
                ),
            )
            self._db.commit()
            return True
        except sqlite3.IntegrityError:
            self._db.rollback()
            return False

    def get_node(self, node_id: str) -> GraphNode | None:
        row = self._db.execute(
            "SELECT * FROM graph_nodes WHERE node_id=?",
            (node_id,),
        ).fetchone()
        if row is None:
            return None
        return GraphNode(
            row["node_id"],
            row["kind"],
            row["tenant_id"],
            row["workspace_id"],
            row["source_id"],
            json.loads(row["payload"]),
            row["content_hash"],
            datetime.fromisoformat(row["observed_at"]),
        )

    def neighbors(
        self, node_id: str, *, kinds: set[EdgeKind] | None = None
    ) -> tuple[GraphEdge, ...]:
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            rows = self._db.execute(
                f"SELECT * FROM graph_edges WHERE from_id=? AND kind IN ({placeholders})",
                (node_id, *sorted(kinds)),
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM graph_edges WHERE from_id=?", (node_id,)
            ).fetchall()
        return tuple(
            GraphEdge(
                row["edge_id"],
                row["tenant_id"],
                row["workspace_id"],
                row["from_id"],
                row["to_id"],
                row["kind"],
                row["confidence"],
                tuple(json.loads(row["provenance_ids"])),
                datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        )

    def nodes(self, *, kind: NodeKind | None = None, limit: int = 1000) -> tuple[GraphNode, ...]:
        query = "SELECT * FROM graph_nodes"
        params: tuple[Any, ...] = ()
        if kind:
            query += " WHERE kind=?"
            params = (kind,)
        rows = self._db.execute(
            query + " ORDER BY observed_at DESC LIMIT ?", (*params, limit)
        ).fetchall()
        return tuple(
            GraphNode(
                row["node_id"],
                row["kind"],
                row["tenant_id"],
                row["workspace_id"],
                row["source_id"],
                json.loads(row["payload"]),
                row["content_hash"],
                datetime.fromisoformat(row["observed_at"]),
            )
            for row in rows
        )


def deterministic_entity_id(entity_type: str, canonical_name: str) -> str:
    value = f"{entity_type}:{canonical_name.strip().casefold()}"
    return "entity:" + hashlib.sha256(value.encode()).hexdigest()[:32]

"""Append-only raw evidence and evidence graph primitives for G1."""
from __future__ import annotations
import hashlib, json, sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

@dataclass(frozen=True)
class RawEvidence:
    evidence_id: str
    source_id: str
    source_record_id: str
    collected_at: datetime
    payload_hash: str
    payload: dict[str, Any]
    schema_version: str = "g1.v1"
    connector_version: str = "unknown"
    @classmethod
    def from_payload(cls, *, evidence_id: str, source_id: str, source_record_id: str,
                     payload: dict[str, Any], connector_version: str = "unknown") -> "RawEvidence":
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return cls(evidence_id, source_id, source_record_id, datetime.now(UTC),
                   hashlib.sha256(encoded).hexdigest(), payload, connector_version=connector_version)

@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    node_type: str
    label: str
    evidence_ids: tuple[str, ...] = ()

@dataclass(frozen=True)
class EvidenceRelation:
    relation_id: str
    subject_id: str
    predicate: str
    object_id: str
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 0.5

@dataclass(frozen=True)
class IntelligenceClaim:
    claim_id: str
    statement: str
    evidence_ids: tuple[str, ...]
    entity_ids: tuple[str, ...] = ()
    confidence: float = 0.5

class SQLiteEvidenceStore:
    """Reference append-only store; production deployments can implement the same contracts."""
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS raw_evidence(
          evidence_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, source_record_id TEXT NOT NULL,
          collected_at TEXT NOT NULL, payload_hash TEXT NOT NULL, payload TEXT NOT NULL,
          schema_version TEXT NOT NULL, connector_version TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evidence_nodes(
          node_id TEXT PRIMARY KEY, node_type TEXT NOT NULL, label TEXT NOT NULL, evidence_ids TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evidence_relations(
          relation_id TEXT PRIMARY KEY, subject_id TEXT NOT NULL, predicate TEXT NOT NULL,
          object_id TEXT NOT NULL, evidence_ids TEXT NOT NULL, confidence REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS intelligence_claims(
          claim_id TEXT PRIMARY KEY, statement TEXT NOT NULL, evidence_ids TEXT NOT NULL,
          entity_ids TEXT NOT NULL, confidence REAL NOT NULL);
        """)
        self._db.commit()
    def append_raw(self, item: RawEvidence) -> bool:
        cur = self._db.execute("INSERT OR IGNORE INTO raw_evidence VALUES(?,?,?,?,?,?,?,?)",
            (item.evidence_id,item.source_id,item.source_record_id,item.collected_at.isoformat(),
             item.payload_hash,json.dumps(item.payload,sort_keys=True),item.schema_version,item.connector_version))
        self._db.commit(); return cur.rowcount == 1
    def add_node(self, node: EvidenceNode) -> bool:
        cur=self._db.execute("INSERT OR IGNORE INTO evidence_nodes VALUES(?,?,?,?)",
            (node.node_id,node.node_type,node.label,json.dumps(node.evidence_ids)))
        self._db.commit(); return cur.rowcount == 1
    def add_relation(self, relation: EvidenceRelation) -> bool:
        cur=self._db.execute("INSERT OR IGNORE INTO evidence_relations VALUES(?,?,?,?,?,?)",
            (relation.relation_id,relation.subject_id,relation.predicate,relation.object_id,
             json.dumps(relation.evidence_ids),relation.confidence))
        self._db.commit(); return cur.rowcount == 1
    def add_claim(self, claim: IntelligenceClaim) -> bool:
        if not claim.evidence_ids: raise ValueError("claim requires evidence")
        cur=self._db.execute("INSERT OR IGNORE INTO intelligence_claims VALUES(?,?,?,?,?)",
            (claim.claim_id,claim.statement,json.dumps(claim.evidence_ids),json.dumps(claim.entity_ids),claim.confidence))
        self._db.commit(); return cur.rowcount == 1
    def count(self, table: str) -> int:
        if table not in {"raw_evidence","evidence_nodes","evidence_relations","intelligence_claims"}:
            raise ValueError("unsupported table")
        return int(self._db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

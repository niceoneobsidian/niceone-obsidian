"""Immutable raw source evidence with deterministic content hashes."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class RawEvidence:
    evidence_id: str
    tenant_id: str
    workspace_id: str
    source_id: str
    source_record_id: str
    payload: Any
    payload_hash: str
    collected_at: datetime
    connector_version: str
    schema_version: str
    ingestion_run_id: str


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class RawEvidenceWriter(Protocol):
    def append(self, evidence: RawEvidence) -> bool: ...


class SQLiteRawEvidenceWriter:
    """Append-only reference implementation; duplicates are rejected by evidence_id/hash."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.execute("""CREATE TABLE IF NOT EXISTS raw_evidence (
            evidence_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
            source_id TEXT NOT NULL, source_record_id TEXT NOT NULL, payload TEXT NOT NULL,
            payload_hash TEXT NOT NULL, collected_at TEXT NOT NULL, connector_version TEXT NOT NULL,
            schema_version TEXT NOT NULL, ingestion_run_id TEXT NOT NULL,
            UNIQUE(tenant_id, workspace_id, source_id, source_record_id, payload_hash)
        )""")
        self._db.commit()

    def append(self, evidence: RawEvidence) -> bool:
        if canonical_hash(evidence.payload) != evidence.payload_hash:
            raise ValueError("payload_hash does not match canonical payload")
        try:
            self._db.execute(
                "INSERT INTO raw_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    evidence.evidence_id,
                    evidence.tenant_id,
                    evidence.workspace_id,
                    evidence.source_id,
                    evidence.source_record_id,
                    json.dumps(evidence.payload, sort_keys=True, default=str),
                    evidence.payload_hash,
                    evidence.collected_at.isoformat(),
                    evidence.connector_version,
                    evidence.schema_version,
                    evidence.ingestion_run_id,
                ),
            )
            self._db.commit()
            return True
        except sqlite3.IntegrityError:
            self._db.rollback()
            return False

    def get(self, evidence_id: str) -> RawEvidence | None:
        row = self._db.execute(
            "SELECT * FROM raw_evidence WHERE evidence_id=?", (evidence_id,)
        ).fetchone()
        if row is None:
            return None
        return RawEvidence(
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            json.loads(row[5]),
            row[6],
            datetime.fromisoformat(row[7]),
            row[8],
            row[9],
            row[10],
        )

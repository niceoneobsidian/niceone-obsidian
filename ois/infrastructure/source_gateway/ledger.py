"""Atomic Phase 1 source ledger.

Raw evidence and its outbox notification share one database transaction.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from .evidence import RawEvidence, canonical_hash
from .outbox import OutboxEvent


class SQLiteSourceLedger:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS raw_evidence (
            evidence_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
            source_id TEXT NOT NULL, source_record_id TEXT NOT NULL, payload TEXT NOT NULL,
            payload_hash TEXT NOT NULL, collected_at TEXT NOT NULL, connector_version TEXT NOT NULL,
            schema_version TEXT NOT NULL, ingestion_run_id TEXT NOT NULL,
            UNIQUE(tenant_id, workspace_id, source_id, source_record_id, payload_hash)
        );
        CREATE TABLE IF NOT EXISTS outbox (
            event_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
            event_type TEXT NOT NULL, aggregate_id TEXT NOT NULL, payload TEXT NOT NULL,
            created_at TEXT NOT NULL, published_at TEXT
        );
        """)
        self._db.commit()

    def commit_ingest(self, evidence: RawEvidence, event: OutboxEvent) -> bool:
        if canonical_hash(evidence.payload) != evidence.payload_hash:
            raise ValueError("payload_hash does not match canonical payload")
        if evidence.tenant_id != event.tenant_id or evidence.workspace_id != event.workspace_id:
            raise PermissionError("evidence and outbox event scopes differ")
        try:
            self._db.execute("BEGIN")
            self._db.execute(
                "INSERT INTO raw_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (evidence.evidence_id, evidence.tenant_id, evidence.workspace_id, evidence.source_id,
                 evidence.source_record_id, json.dumps(evidence.payload, sort_keys=True, default=str),
                 evidence.payload_hash, evidence.collected_at.isoformat(), evidence.connector_version,
                 evidence.schema_version, evidence.ingestion_run_id),
            )
            self._db.execute(
                "INSERT INTO outbox VALUES (?,?,?,?,?,?,?,NULL)",
                (event.event_id, event.tenant_id, event.workspace_id, event.event_type,
                 event.aggregate_id, json.dumps(event.payload, sort_keys=True), event.created_at.isoformat()),
            )
            self._db.commit()
            return True
        except sqlite3.IntegrityError:
            self._db.rollback()
            return False
        except Exception:
            self._db.rollback()
            raise

    def pending(self, *, limit: int = 100) -> tuple[OutboxEvent, ...]:
        rows = self._db.execute(
            "SELECT * FROM outbox WHERE published_at IS NULL ORDER BY created_at, event_id LIMIT ?",
            (limit,),
        ).fetchall()
        return tuple(
            OutboxEvent(r[0], r[1], r[2], r[3], r[4], json.loads(r[5]), datetime.fromisoformat(r[6]))
            for r in rows
        )

    def mark_published(self, event_id: str) -> None:
        self._db.execute("UPDATE outbox SET published_at=CURRENT_TIMESTAMP WHERE event_id=?", (event_id,))
        self._db.commit()

    def evidence(self, evidence_id: str) -> RawEvidence | None:
        row = self._db.execute("SELECT * FROM raw_evidence WHERE evidence_id=?", (evidence_id,)).fetchone()
        if row is None:
            return None
        return RawEvidence(
            row[0], row[1], row[2], row[3], row[4], json.loads(row[5]), row[6],
            datetime.fromisoformat(row[7]), row[8], row[9], row[10],
        )

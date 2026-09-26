"""Durable semantic-world repository with versioned facts, provenance, and retrieval."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class WorldEntity:
    entity_id: str
    entity_type: str
    attributes: dict[str, Any]
    version: int


@dataclass(frozen=True)
class WorldFact:
    fact_id: str
    subject_id: str
    predicate: str
    object_value: Any
    source: str
    confidence: float
    version: int
    observed_at: datetime


class KnowledgeWorldStore:
    """Append-only fact history with versioned entity projection and provenance."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.db = connection
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS world_entities ("
            "entity_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, "
            "attributes_json TEXT NOT NULL, version INTEGER NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS world_facts ("
            "fact_id TEXT PRIMARY KEY, subject_id TEXT NOT NULL, predicate TEXT NOT NULL, "
            "object_json TEXT NOT NULL, source TEXT NOT NULL, confidence REAL NOT NULL, "
            "version INTEGER NOT NULL, observed_at TEXT NOT NULL)"
        )
        self.db.commit()

    def upsert_entity(
        self, entity_id: str, entity_type: str, attributes: dict[str, Any]
    ) -> WorldEntity:
        row = self.db.execute(
            "SELECT version FROM world_entities WHERE entity_id=?", (entity_id,)
        ).fetchone()
        version = int(row[0]) + 1 if row else 1
        self.db.execute(
            "INSERT INTO world_entities(entity_id,entity_type,attributes_json,version) "
            "VALUES (?,?,?,?) ON CONFLICT(entity_id) DO UPDATE SET "
            "entity_type=excluded.entity_type, attributes_json=excluded.attributes_json, "
            "version=excluded.version",
            (entity_id, entity_type, json.dumps(attributes, sort_keys=True), version),
        )
        self.db.commit()
        return WorldEntity(entity_id, entity_type, dict(attributes), version)

    def assert_fact(
        self,
        subject_id: str,
        predicate: str,
        object_value: Any,
        *,
        source: str,
        confidence: float = 1.0,
    ) -> WorldFact:
        if not source:
            raise ValueError("fact provenance source is required")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        row = self.db.execute(
            "SELECT COALESCE(MAX(version),0) FROM world_facts WHERE subject_id=? AND predicate=?",
            (subject_id, predicate),
        ).fetchone()
        version = int(row[0]) + 1
        fact_id = f"{subject_id}:{predicate}:{version}"
        observed = datetime.now(UTC)
        self.db.execute(
            "INSERT INTO world_facts VALUES (?,?,?,?,?,?,?,?)",
            (fact_id, subject_id, predicate, json.dumps(object_value, sort_keys=True, default=str),
             source, confidence, version, observed.isoformat()),
        )
        self.db.commit()
        return WorldFact(
            fact_id, subject_id, predicate, object_value, source, confidence, version, observed
        )

    def facts(self, subject_id: str, predicate: str | None = None) -> tuple[WorldFact, ...]:
        sql = "SELECT * FROM world_facts WHERE subject_id=?"
        params: list[Any] = [subject_id]
        if predicate is not None:
            sql += " AND predicate=?"
            params.append(predicate)
        sql += " ORDER BY version"
        rows = self.db.execute(sql, params).fetchall()
        return tuple(
            WorldFact(
                r[0], r[1], r[2], json.loads(r[3]), r[4], float(r[5]), int(r[6]),
                datetime.fromisoformat(r[7]),
            )
            for r in rows
        )

    def query(self, predicate: str, object_value: Any) -> tuple[WorldFact, ...]:
        rows = self.db.execute(
            "SELECT * FROM world_facts WHERE predicate=? ORDER BY observed_at", (predicate,)
        ).fetchall()
        return tuple(
            WorldFact(
                r[0], r[1], r[2], json.loads(r[3]), r[4], float(r[5]), int(r[6]),
                datetime.fromisoformat(r[7]),
            )
            for r in rows
            if json.loads(r[3]) == object_value
        )

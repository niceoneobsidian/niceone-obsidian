from __future__ import annotations

from typing import Any
from uuid import UUID

from .world import KnowledgeAssertion, SemanticWorldStore, WorldEntity, WorldRelation


class PostgresSemanticWorldStore(SemanticWorldStore):
    """Durable PostgreSQL adapter for ground state and separately learned assertions."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN is required")
        self._dsn = dsn

    def _connect(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL persistence requires the 'psycopg' package") from exc
        return psycopg.connect(self._dsn)

    def put_entity(self, entity: WorldEntity) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO ois_world_entities
                (entity_id, tenant, entity_type, canonical_name, attributes, provenance_refs, observed_at, version)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                ON CONFLICT (entity_id) DO UPDATE SET
                  canonical_name=EXCLUDED.canonical_name,
                  attributes=EXCLUDED.attributes,
                  provenance_refs=EXCLUDED.provenance_refs,
                  observed_at=EXCLUDED.observed_at,
                  version=EXCLUDED.version
                WHERE ois_world_entities.tenant=EXCLUDED.tenant
                  AND EXCLUDED.version > ois_world_entities.version""",
                (str(entity.entity_id), entity.tenant, entity.entity_type, entity.canonical_name,
                 entity.attributes, entity.provenance_refs, entity.observed_at, entity.version),
            )

    def put_relation(self, relation: WorldRelation) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO ois_world_relations
                (relation_id,tenant,subject_id,predicate,object_id,provenance_refs,valid_from,valid_until,confidence)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (relation_id) DO NOTHING""",
                (str(relation.relation_id), relation.tenant, str(relation.subject_id), relation.predicate,
                 str(relation.object_id), relation.provenance_refs, relation.valid_from,
                 relation.valid_until, relation.confidence),
            )

    def put_assertion(self, assertion: KnowledgeAssertion) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO ois_knowledge_assertions
                (assertion_id,tenant,subject_id,predicate,value,evidence_refs,confidence,authority,valid_from,valid_until,version)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (assertion_id) DO NOTHING""",
                (str(assertion.assertion_id), assertion.tenant, str(assertion.subject_id), assertion.predicate,
                 assertion.value, assertion.evidence_refs, assertion.confidence, assertion.authority,
                 assertion.valid_from, assertion.valid_until, assertion.version),
            )

    def get_entity(self, entity_id: UUID, *, tenant: str) -> WorldEntity | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT entity_id,tenant,entity_type,canonical_name,attributes,provenance_refs,observed_at,version
                FROM ois_world_entities WHERE entity_id=%s AND tenant=%s""",
                (str(entity_id), tenant),
            ).fetchone()
        return WorldEntity.model_validate(_entity_row(row)) if row else None

    def relations(self, entity_id: UUID, *, tenant: str) -> tuple[WorldRelation, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT relation_id,tenant,subject_id,predicate,object_id,provenance_refs,valid_from,valid_until,confidence
                FROM ois_world_relations WHERE tenant=%s AND (subject_id=%s OR object_id=%s)""",
                (tenant, str(entity_id), str(entity_id)),
            ).fetchall()
        return tuple(WorldRelation.model_validate(_relation_row(row)) for row in rows)


def _entity_row(row: tuple[object, ...]) -> dict[str, object]:
    return dict(zip(
        ("entity_id", "tenant", "entity_type", "canonical_name", "attributes", "provenance_refs", "observed_at", "version"),
        row,
        strict=True,
    ))


def _relation_row(row: tuple[object, ...]) -> dict[str, object]:
    return dict(zip(
        ("relation_id", "tenant", "subject_id", "predicate", "object_id", "provenance_refs", "valid_from", "valid_until", "confidence"),
        row,
        strict=True,
    ))

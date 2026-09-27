"""Durable-by-contract semantic world primitives: entities, facts and provenance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Entity:
    entity_id: str
    entity_type: str
    attributes: dict[str, Any]
    version: int


@dataclass(frozen=True)
class Fact:
    fact_id: str
    subject_id: str
    predicate: str
    object_value: Any
    source: str
    confidence: float
    version: int
    observed_at: datetime


class SemanticWorld:
    """Shared world state; writes are versioned and retain provenance."""

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._facts: list[Fact] = []

    def upsert_entity(
        self, entity_type: str, attributes: dict[str, Any], entity_id: str | None = None
    ) -> Entity:
        entity_id = entity_id or str(uuid4())
        old = self._entities.get(entity_id)
        entity = Entity(entity_id, entity_type, dict(attributes), (old.version + 1) if old else 1)
        self._entities[entity_id] = entity
        return entity

    def assert_fact(
        self,
        subject_id: str,
        predicate: str,
        object_value: Any,
        *,
        source: str,
        confidence: float = 1.0,
    ) -> Fact:
        if not source:
            raise ValueError("fact provenance source is required")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        version = 1 + max(
            (
                f.version
                for f in self._facts
                if f.subject_id == subject_id and f.predicate == predicate
            ),
            default=0,
        )
        fact = Fact(
            str(uuid4()), subject_id, predicate, object_value, source, confidence, version, _now()
        )
        self._facts.append(fact)
        return fact

    def entity(self, entity_id: str) -> Entity | None:
        return self._entities.get(entity_id)

    def facts(
        self, subject_id: str | None = None, predicate: str | None = None
    ) -> tuple[Fact, ...]:
        return tuple(
            f
            for f in self._facts
            if (subject_id is None or f.subject_id == subject_id)
            and (predicate is None or f.predicate == predicate)
        )

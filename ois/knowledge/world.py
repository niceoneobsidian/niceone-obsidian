from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class WorldEntity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_id: UUID = Field(default_factory=uuid4)
    tenant: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    attributes: dict[str, Any] = Field(default_factory=dict)
    provenance_refs: tuple[str, ...] = ()
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1


class WorldRelation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    relation_id: UUID = Field(default_factory=uuid4)
    tenant: str = Field(min_length=1)
    subject_id: UUID
    predicate: str = Field(min_length=1)
    object_id: UUID
    provenance_refs: tuple[str, ...] = ()
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class KnowledgeAssertion(BaseModel):
    """Learned/derived knowledge; deliberately separate from ground world state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    assertion_id: UUID = Field(default_factory=uuid4)
    tenant: str = Field(min_length=1)
    subject_id: UUID
    predicate: str = Field(min_length=1)
    value: Any
    evidence_refs: tuple[str, ...] = ()
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    authority: str = "unknown"
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    version: int = 1


class SemanticWorldStore(Protocol):
    def put_entity(self, entity: WorldEntity) -> None: ...
    def put_relation(self, relation: WorldRelation) -> None: ...
    def put_assertion(self, assertion: KnowledgeAssertion) -> None: ...
    def get_entity(self, entity_id: UUID, *, tenant: str) -> WorldEntity | None: ...
    def relations(self, entity_id: UUID, *, tenant: str) -> tuple[WorldRelation, ...]: ...


class InMemorySemanticWorldStore:
    """Reference implementation for deterministic tests and local development."""

    def __init__(self) -> None:
        self.entities: dict[UUID, WorldEntity] = {}
        self.relation_items: dict[UUID, WorldRelation] = {}
        self.assertions: dict[UUID, KnowledgeAssertion] = {}

    def put_entity(self, entity: WorldEntity) -> None:
        self._tenant_guard(self.entities.get(entity.entity_id), entity.tenant)
        current = self.entities.get(entity.entity_id)
        if current is not None and entity.version <= current.version:
            raise ValueError("entity versions must increase")
        self.entities[entity.entity_id] = entity

    def put_relation(self, relation: WorldRelation) -> None:
        self._tenant_guard(self.relation_items.get(relation.relation_id), relation.tenant)
        self.relation_items.setdefault(relation.relation_id, relation)

    def put_assertion(self, assertion: KnowledgeAssertion) -> None:
        self._tenant_guard(self.assertions.get(assertion.assertion_id), assertion.tenant)
        self.assertions.setdefault(assertion.assertion_id, assertion)

    def get_entity(self, entity_id: UUID, *, tenant: str) -> WorldEntity | None:
        entity = self.entities.get(entity_id)
        return entity if entity is not None and entity.tenant == tenant else None

    def relations(self, entity_id: UUID, *, tenant: str) -> tuple[WorldRelation, ...]:
        return tuple(
            relation
            for relation in self.relation_items.values()
            if relation.tenant == tenant
            and (relation.subject_id == entity_id or relation.object_id == entity_id)
        )

    @staticmethod
    def _tenant_guard(current: Any, tenant: str) -> None:
        if current is not None and current.tenant != tenant:
            raise PermissionError("tenant boundary violation")


def content_hash(model: BaseModel) -> str:
    """Stable digest for evidence/provenance of semantic records."""
    encoded = json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()

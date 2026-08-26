from datetime import datetime, timezone

import pytest

from ois.capabilities import register_event_ingestion
from ois.events import EventIngestion, InMemoryEventStore
from ois.knowledge import InMemorySemanticWorldStore, KnowledgeAssertion, WorldEntity, WorldRelation
from ois.kernel.registry import CapabilityRegistry


def test_event_ingestion_hashes_and_persists_canonically() -> None:
    store = InMemoryEventStore()
    capability = EventIngestion(store)
    event = capability.ingest(
        source="git", tenant="tenant-a", actor="user-1", event_type="commit",
        payload={"sha": "abc", "branch": "main"},
        observed_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
        source_ref="git:commit:abc", source_kind="git",
    )
    assert event.validation.valid is True
    assert len(event.content_hash) == 64
    event.assert_integrity()
    assert store.get(event.event_id) == event


def test_event_store_is_idempotent_but_rejects_tampering() -> None:
    store = InMemoryEventStore()
    capability = EventIngestion(store)
    event = capability.ingest(
        source="ci", tenant="tenant-a", actor="runner", event_type="build",
        payload={"status": "passed"}, observed_at=datetime.now(timezone.utc),
        source_ref="ci:1", source_kind="ci",
    )
    store.append(event)
    assert len(store.list(tenant="tenant-a")) == 1
    tampered = event.model_copy(update={"payload": {"status": "failed"}})
    with pytest.raises(ValueError, match="integrity"):
        store.append(tampered)


def test_event_ingestion_is_registry_addressable() -> None:
    registry = CapabilityRegistry()
    capability = register_event_ingestion(registry, InMemoryEventStore())
    assert registry.get("event_ingestion", "1.0.0").capability is capability


def test_semantic_world_separates_ground_state_from_learned_assertions() -> None:
    store = InMemorySemanticWorldStore()
    first = WorldEntity(tenant="tenant-a", entity_type="service", canonical_name="api")
    second = WorldEntity(tenant="tenant-a", entity_type="service", canonical_name="worker")
    store.put_entity(first)
    store.put_entity(second)
    relation = WorldRelation(
        tenant="tenant-a", subject_id=first.entity_id, predicate="depends_on", object_id=second.entity_id
    )
    store.put_relation(relation)
    assertion = KnowledgeAssertion(
        tenant="tenant-a", subject_id=first.entity_id, predicate="likely_failure_mode",
        value="timeout", evidence_refs=("event:123",), confidence=0.7,
    )
    store.put_assertion(assertion)
    assert store.get_entity(first.entity_id, tenant="tenant-a") == first
    assert store.relations(first.entity_id, tenant="tenant-a") == (relation,)
    assert store.assertions[assertion.assertion_id] == assertion


def test_semantic_world_enforces_tenant_boundary() -> None:
    store = InMemorySemanticWorldStore()
    entity = WorldEntity(tenant="tenant-a", entity_type="user", canonical_name="alice")
    store.put_entity(entity)
    assert store.get_entity(entity.entity_id, tenant="tenant-b") is None
    relation = WorldRelation(
        tenant="tenant-b", subject_id=entity.entity_id, predicate="owns", object_id=entity.entity_id
    )
    with pytest.raises(PermissionError, match="tenant"):
        store.put_relation(relation)

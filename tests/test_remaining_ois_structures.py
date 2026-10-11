from __future__ import annotations

import sqlite3

import pytest

from ois.infrastructure.source_gateway.contracts import SourceProvenance
from production.knowledge_world import KnowledgeWorldStore
from production.model_gateway import ModelGateway, ModelRequest, ModelSpec
from production.production_loop import STAGES, LoopArtifact, ProductionLoopProof


class FakeModel:
    def generate(self, *, model: str, prompt: str, **kwargs: object) -> dict[str, str]:
        return {"model": model, "text": prompt}


def test_model_gateway_fallback_and_budget() -> None:
    gateway = ModelGateway()
    generation = frozenset({"generation"})
    gateway.register(ModelSpec("primary", "1", FakeModel(), generation, priority=10))
    gateway.register(ModelSpec("fallback", "1", FakeModel(), generation, priority=20))
    gateway.set_health("primary", "1", False)
    result = gateway.invoke(ModelRequest("generation", "hello"))
    assert result.model_id == "fallback"
    assert result.fallback_used


def test_model_gateway_honors_preferred_model_before_priority() -> None:
    gateway = ModelGateway()
    generation = frozenset({"generation"})
    gateway.register(
        ModelSpec("fast", "1", FakeModel(), generation, priority=1, cost_per_1k_tokens=0.01)
    )
    gateway.register(
        ModelSpec("preferred", "1", FakeModel(), generation, priority=50, cost_per_1k_tokens=0.02)
    )
    result = gateway.invoke(
        ModelRequest("generation", "hello", preferred_model="preferred", budget=1.0)
    )
    assert result.model_id == "preferred"
    assert not result.fallback_used


def test_model_gateway_falls_back_when_preferred_model_is_unhealthy() -> None:
    gateway = ModelGateway()
    generation = frozenset({"generation"})
    gateway.register(ModelSpec("preferred", "1", FakeModel(), generation, priority=1))
    gateway.register(ModelSpec("backup", "1", FakeModel(), generation, priority=10))
    gateway.set_health("preferred", "1", False)
    result = gateway.invoke(ModelRequest("generation", "hello", preferred_model="preferred"))
    assert result.model_id == "backup"
    assert result.fallback_used


@pytest.mark.parametrize("budget", [-1.0, float("nan"), float("inf")])
def test_model_request_rejects_invalid_budget(budget: float) -> None:
    with pytest.raises(ValueError, match="budget"):
        ModelRequest("generation", "hello", budget=budget)


def test_knowledge_world_is_versioned_and_provenanced() -> None:
    store = KnowledgeWorldStore(sqlite3.connect(":memory:"))
    first = store.upsert_entity("post-1", "post", {"topic": "ai"})
    second = store.upsert_entity("post-1", "post", {"topic": "growth"})
    assert (first.version, second.version) == (1, 2)
    fact = store.assert_fact(
        "post-1",
        "platform",
        "tiktok",
        source="live:tiktok",
        confidence=0.99,
    )
    assert fact.version == 1
    assert store.facts("post-1")[0].source == "live:tiktok"
    assert store.query("platform", "tiktok") == (fact,)


def test_knowledge_world_rejects_empty_provenance_and_invalid_confidence() -> None:
    store = KnowledgeWorldStore(sqlite3.connect(":memory:"))
    with pytest.raises(ValueError, match="provenance"):
        store.assert_fact("post-1", "platform", "tiktok", source=" ")
    with pytest.raises(ValueError, match="confidence"):
        store.assert_fact(
            "post-1", "platform", "tiktok", source="test", confidence=float("inf")
        )


def test_source_provenance_redacts_nested_credentials_without_mutating_input() -> None:
    metadata = {
        "page": {"title": "Public title", "api_key": "do-not-store"},
        "access-token": "also-secret",
        "result_count": 3,
        "items": [{"authorization": "Bearer secret", "name": "safe"}],
    }
    provenance = SourceProvenance(
        provider="example",
        endpoint="/items",
        operation="list",
        request_id="req-1",
        metadata=metadata,
    ).as_dict()
    assert provenance["metadata"] == {
        "page": {"title": "Public title", "api_key": "[REDACTED]"},
        "access-token": "[REDACTED]",
        "result_count": 3,
        "items": [{"authorization": "[REDACTED]", "name": "safe"}],
    }
    assert metadata["page"]["api_key"] == "do-not-store"


def test_production_loop_fails_closed_until_all_stages_exist() -> None:
    proof = ProductionLoopProof()
    partial = tuple(
        LoopArtifact.create(
            stage,
            stage,
            "tenant-a",
            {"stage": stage},
            source_ref=f"live:{stage}",
            execution_id="exec-1",
        )
        for stage in STAGES[:-1]
    )
    rejected = proof.certify(
        certificate_id="cert-1",
        tenant_id="tenant-a",
        execution_id="exec-1",
        artifacts=partial,
    )
    assert not rejected.production_verified

    complete = partial + (
        LoopArtifact.create(
            "learning",
            "learning",
            "tenant-a",
            {"stage": "learning"},
            source_ref="live:learning",
            execution_id="exec-1",
        ),
    )
    certified = proof.certify(
        certificate_id="cert-2",
        tenant_id="tenant-a",
        execution_id="exec-1",
        artifacts=complete,
    )
    assert certified.production_verified
    assert len(certified.lineage_hash) == 64

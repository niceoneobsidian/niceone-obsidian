from __future__ import annotations

import sqlite3

from production.knowledge_world import KnowledgeWorldStore
from production.model_gateway import ModelGateway, ModelRequest, ModelSpec
from production.production_loop import LoopArtifact, ProductionLoopProof, STAGES


class FakeModel:
    def generate(self, *, model: str, prompt: str, **kwargs: object) -> dict[str, str]:
        return {"model": model, "text": prompt}


def test_model_gateway_fallback_and_budget() -> None:
    gateway = ModelGateway()
    gateway.register(
        ModelSpec("primary", "1", FakeModel(), frozenset({"generation"}), priority=10)
    )
    gateway.register(
        ModelSpec("fallback", "1", FakeModel(), frozenset({"generation"}), priority=20)
    )
    gateway.set_health("primary", "1", False)
    result = gateway.invoke(ModelRequest("generation", "hello"))
    assert result.model_id == "fallback"
    assert result.fallback_used


def test_knowledge_world_is_versioned_and_provenanced() -> None:
    store = KnowledgeWorldStore(sqlite3.connect(":memory:"))
    first = store.upsert_entity("post-1", "post", {"topic": "ai"})
    second = store.upsert_entity("post-1", "post", {"topic": "growth"})
    assert (first.version, second.version) == (1, 2)
    fact = store.assert_fact(
        "post-1", "platform", "tiktok", source="live:tiktok", confidence=0.99
    )
    assert fact.version == 1
    assert store.facts("post-1")[0].source == "live:tiktok"


def test_production_loop_fails_closed_until_all_stages_exist() -> None:
    proof = ProductionLoopProof()
    partial = tuple(
        LoopArtifact.create(
            stage, stage, "tenant-a", {"stage": stage},
            source_ref=f"live:{stage}", execution_id="exec-1"
        )
        for stage in STAGES[:-1]
    )
    rejected = proof.certify(
        certificate_id="cert-1", tenant_id="tenant-a", execution_id="exec-1", artifacts=partial
    )
    assert not rejected.production_verified

    complete = partial + (
        LoopArtifact.create(
            "learning", "learning", "tenant-a", {"stage": "learning"},
            source_ref="live:learning", execution_id="exec-1"
        ),
    )
    certified = proof.certify(
        certificate_id="cert-2", tenant_id="tenant-a", execution_id="exec-1", artifacts=complete
    )
    assert certified.production_verified
    assert len(certified.lineage_hash) == 64

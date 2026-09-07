from __future__ import annotations

import pytest

from ois.evolution.controlled import EvolutionProposal, EvolutionState, ControlledEvolution
from ois.governance.hitl import ApprovalRequest, ApprovalState, HITLGate
from ois.governance.sandbox import SandboxAuthorizer, SandboxDenied, SandboxPolicy, SandboxRequest
from ois.knowledge.store import KnowledgeStore, new_assertion
from ois.fabric import OISFabric


class Provider:
    def __init__(self, value: object) -> None:
        self.value = value

    def invoke(self, *args: object, **kwargs: object) -> object:
        return self.value


def test_fabric_uses_canonical_versioned_registries() -> None:
    fabric = OISFabric()
    fabric.register_agent("agent.research", "1.0.0", Provider("agent"))
    fabric.register_tool("tool.search", "1.0.0", Provider({"results": 1}))
    fabric.register_model("model.test", "1.0.0", Provider("answer"))
    assert fabric.select_agent("agent.research", "1.0.0").agent_id == "agent.research"
    assert fabric.invoke_tool("tool.search", "1.0.0", {}) == {"results": 1}
    assert fabric.invoke_model("model.test", "1.0.0", "hello") == "answer"


def test_hitl_requires_identity_and_never_replaces_policy() -> None:
    gate = HITLGate()
    gate.request(ApprovalRequest(
        "a1", "e1", "t1", "publish", "1.0.0", "publish one post", "2026-09-06T00:00:00Z", "2026-09-07T00:00:00Z"
    ))
    assert gate.authorize("a1") is False
    decision = gate.decide("a1", approved=True, actor="human-1")
    assert decision.state is ApprovalState.APPROVED
    assert gate.authorize("a1") is True


def test_sandbox_denies_network_and_unknown_modules() -> None:
    authorizer = SandboxAuthorizer(SandboxPolicy())
    with pytest.raises(SandboxDenied):
        authorizer.authorize(SandboxRequest("python", "print(1)", network=True))
    with pytest.raises(SandboxDenied):
        authorizer.authorize(SandboxRequest("python", "import os", modules=frozenset({"os"})))


def test_knowledge_keeps_ground_and_learned_assertions_separate() -> None:
    store = KnowledgeStore()
    store.append(new_assertion("g1", "t1", "topic", "is", "ground", "source-1"))
    store.append(new_assertion("l1", "t1", "topic", "predicts", "learned", "trace-1", confidence=0.7, learned=True))
    assert len(store.ground("t1", "topic")) == 1
    assert len(store.learned("t1", "topic")) == 1
    assert store.ground("t2", "topic") == ()


def test_controlled_evolution_requires_evidence_evaluation_and_rollback() -> None:
    engine = ControlledEvolution()
    engine.propose(EvolutionProposal("p1", "router", "1.0", "1.1", ("ev-1",)))
    evaluated = engine.evaluate("p1", 0.9, minimum=0.8)
    assert evaluated.state is EvolutionState.EVALUATED
    engine.approve("p1", actor="release-manager")
    engine.canary("p1")
    promoted = engine.promote("p1", rollback_verified=True)
    assert promoted.state is EvolutionState.PROMOTED
    assert engine.rollback("p1").state is EvolutionState.ROLLED_BACK

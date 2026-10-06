from ois.governance import (
    ActionBudget,
    ActionLimit,
    AgentIdentity,
    CapabilityGrant,
    GovernanceEngine,
    InMemoryGovernanceStore,
    PolicyVersion,
)


def test_governance_authorizes_and_records_provenance() -> None:
    store = InMemoryGovernanceStore()
    store.put_agent(AgentIdentity("agent-1", "tenant-a", "operator"))
    store.grant(CapabilityGrant("cap.write", "tenant-a", "agent-1", ("write",)))
    store.put_policy(PolicyVersion("default", "1", "tenant-a", {"write": "allow"}, "hash-1"))
    engine = GovernanceEngine(store)
    result = engine.authorize(
        tenant_id="tenant-a",
        workspace_id="ws-a",
        execution_id="exec-a",
        agent_id="agent-1",
        action="write",
        capability_id="cap.write",
        inputs={"x": 1},
        policy_id="default",
        policy_version="1",
    )
    assert result.allowed
    assert len(store.decisions) == 1
    assert store.decisions[0].inputs_digest
    assert store.audit[0].outcome == "allowed"
    assert store.decisions[0].policy_id == "default"
    assert store.decisions[0].policy_version == "1"


def test_tenant_isolation_denies_cross_tenant_agent() -> None:
    store = InMemoryGovernanceStore()
    store.put_agent(AgentIdentity("agent-1", "tenant-a", "operator"))
    store.grant(CapabilityGrant("cap.write", "tenant-a", "agent-1", ("write",)))
    result = GovernanceEngine(store).authorize(
        tenant_id="tenant-b",
        workspace_id="ws-b",
        execution_id="exec-b",
        agent_id="agent-1",
        action="write",
        capability_id="cap.write",
        inputs={},
    )
    assert not result.allowed
    assert "identity" in result.reason


def test_action_limit_is_fail_closed() -> None:
    store = InMemoryGovernanceStore()
    store.put_agent(AgentIdentity("agent-1", "tenant-a", "operator"))
    store.grant(CapabilityGrant("cap.write", "tenant-a", "agent-1", ("write",)))
    store.put_limit(ActionLimit("tenant-a", "write", max_count=1))
    engine = GovernanceEngine(store)
    kwargs = dict(
        tenant_id="tenant-a",
        workspace_id="ws-a",
        execution_id="e",
        agent_id="agent-1",
        action="write",
        capability_id="cap.write",
        inputs={},
    )
    assert engine.authorize(**kwargs).allowed
    assert not engine.authorize(**kwargs).allowed


def test_budget_blocks_overspend() -> None:
    store = InMemoryGovernanceStore()
    store.put_agent(AgentIdentity("agent-1", "tenant-a", "operator"))
    store.grant(CapabilityGrant("cap.write", "tenant-a", "agent-1", ("write",)))
    store.put_budget(ActionBudget("tenant-a", "b1", max_cost=1.0))
    engine = GovernanceEngine(store)
    result = engine.authorize(
        tenant_id="tenant-a",
        workspace_id="ws-a",
        execution_id="e",
        agent_id="agent-1",
        action="write",
        capability_id="cap.write",
        inputs={},
        estimated_cost=2.0,
    )
    assert not result.allowed
    assert "budget" in result.reason


def test_inactive_policy_version_fails_closed() -> None:
    store = InMemoryGovernanceStore()
    store.put_agent(AgentIdentity("agent-1", "tenant-a", "operator"))
    store.grant(CapabilityGrant("cap.write", "tenant-a", "agent-1", ("write",)))
    store.put_policy(
        PolicyVersion("default", "2", "tenant-a", {"write": "allow"}, "hash-2", active=False)
    )
    result = GovernanceEngine(store).authorize(
        tenant_id="tenant-a",
        workspace_id="ws-a",
        execution_id="e",
        agent_id="agent-1",
        action="write",
        capability_id="cap.write",
        inputs={},
        policy_id="default",
        policy_version="2",
    )
    assert not result.allowed
    assert "policy" in result.reason

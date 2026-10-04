import pytest

from ois.governance import (
    ActionBudget,
    ActionLimit,
    AgentIdentity,
    CapabilityGrant,
    GovernanceEngine,
    InMemoryGovernanceStore,
)


def configured() -> tuple[InMemoryGovernanceStore, GovernanceEngine]:
    store = InMemoryGovernanceStore()
    store.put_agent(AgentIdentity("agent", "tenant", "operator"))
    store.grant(CapabilityGrant("cap", "tenant", "agent", ("mutate",)))
    return store, GovernanceEngine(store)


def test_missing_grant_is_fail_closed() -> None:
    store = InMemoryGovernanceStore()
    store.put_agent(AgentIdentity("agent", "tenant", "operator"))
    result = GovernanceEngine(store).authorize(
        tenant_id="tenant", workspace_id="w", execution_id="e",
        agent_id="agent", action="mutate", capability_id="missing", inputs={}
    )
    assert not result.allowed


def test_expired_grant_is_rejected() -> None:
    from datetime import UTC, datetime, timedelta
    store = InMemoryGovernanceStore()
    store.put_agent(AgentIdentity("agent", "tenant", "operator"))
    store.grant(
        CapabilityGrant(
            "cap", "tenant", "agent", ("mutate",),
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    result = GovernanceEngine(store).authorize(
        tenant_id="tenant", workspace_id="w", execution_id="e",
        agent_id="agent", action="mutate", capability_id="cap", inputs={}
    )
    assert not result.allowed


def test_action_and_budget_limits_are_independent() -> None:
    store, engine = configured()
    store.put_limit(ActionLimit("tenant", "mutate", 1))
    store.put_budget(ActionBudget("tenant", "budget", 1))
    first = engine.authorize(
        tenant_id="tenant", workspace_id="w", execution_id="e1",
        agent_id="agent", action="mutate", capability_id="cap", inputs={}, estimated_cost=.5
    )
    second = engine.authorize(
        tenant_id="tenant", workspace_id="w", execution_id="e2",
        agent_id="agent", action="mutate", capability_id="cap", inputs={}, estimated_cost=.5
    )
    assert first.allowed
    assert not second.allowed
    assert "limit" in second.reason


@pytest.mark.parametrize("bad_tenant", ["other", ""])
def test_tenant_boundary_rejects_unknown_tenant(bad_tenant: str) -> None:
    store, engine = configured()
    result = engine.authorize(
        tenant_id=bad_tenant, workspace_id="w", execution_id="e",
        agent_id="agent", action="mutate", capability_id="cap", inputs={}
    )
    assert not result.allowed

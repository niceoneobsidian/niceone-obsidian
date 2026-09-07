from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ois.hitl import HITLBindingError, HITLGate, HITLAuthorizationError, HITLStatus
from ois.sandbox import SandboxPolicy, SandboxPolicyError
from ois.security import TenantContextError, validate_tenant_id


def test_hitl_approval_is_bound_to_exact_action_and_plan() -> None:
    tenant_id = uuid4()
    execution_id = uuid4()
    gate = HITLGate.create(
        gate_id=uuid4(),
        execution_id=execution_id,
        tenant_id=tenant_id,
        action_type="external.write",
        required_role="secops_admin",
        proposed_side_effect={"destination": "vault-01", "amount": 750000},
        plan_hash="a" * 64,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    with pytest.raises(HITLBindingError):
        gate.resolve(
            tenant_id=tenant_id,
            execution_id=execution_id,
            action_type="external.write",
            plan_hash="b" * 64,
            reviewer_id=uuid4(),
            reviewer_roles={"secops_admin"},
            decision=HITLStatus.APPROVED,
        )


def test_hitl_requires_role_and_fails_closed() -> None:
    tenant_id = uuid4()
    execution_id = uuid4()
    gate = HITLGate.create(
        gate_id=uuid4(),
        execution_id=execution_id,
        tenant_id=tenant_id,
        action_type="external.write",
        required_role="secops_admin",
        proposed_side_effect={"amount": 1},
        plan_hash="a" * 64,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    with pytest.raises(HITLAuthorizationError):
        gate.resolve(
            tenant_id=tenant_id,
            execution_id=execution_id,
            action_type="external.write",
            plan_hash="a" * 64,
            reviewer_id=uuid4(),
            reviewer_roles={"viewer"},
            decision=HITLStatus.APPROVED,
        )


def test_hitl_detects_mutated_side_effect() -> None:
    gate = HITLGate.create(
        gate_id=uuid4(),
        execution_id=uuid4(),
        tenant_id=uuid4(),
        action_type="external.write",
        required_role="secops_admin",
        proposed_side_effect={"amount": 750000},
        plan_hash="a" * 64,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with pytest.raises(HITLBindingError):
        gate.verify_side_effect({"amount": 750001})


def test_expired_hitl_gate_cannot_be_approved() -> None:
    now = datetime.now(UTC)
    gate = HITLGate.create(
        gate_id=uuid4(),
        execution_id=uuid4(),
        tenant_id=uuid4(),
        action_type="external.write",
        required_role="secops_admin",
        proposed_side_effect={"amount": 1},
        plan_hash="a" * 64,
        expires_at=now - timedelta(seconds=1),
    )
    resolved = gate.resolve(
        tenant_id=gate.tenant_id,
        execution_id=gate.execution_id,
        action_type=gate.action_type,
        plan_hash=gate.plan_hash,
        reviewer_id=uuid4(),
        reviewer_roles={"secops_admin"},
        decision=HITLStatus.APPROVED,
        now=now,
    )
    assert resolved.status is HITLStatus.EXPIRED


def test_sandbox_defaults_to_no_network_or_filesystem_writes() -> None:
    policy = SandboxPolicy()
    with pytest.raises(SandboxPolicyError):
        policy.validate_request(hosts={"example.com"})
    with pytest.raises(SandboxPolicyError):
        policy.validate_request(paths={"/tmp/output"})


def test_sandbox_allows_only_declared_resources() -> None:
    policy = SandboxPolicy(
        allowed_modules=frozenset({"json"}),
        allowed_hosts=frozenset({"api.example.com"}),
        network_enabled=True,
    )
    policy.validate_request(modules={"json"}, hosts={"api.example.com"})
    with pytest.raises(SandboxPolicyError):
        policy.validate_request(modules={"os"})


def test_tenant_id_validation_is_fail_closed() -> None:
    assert validate_tenant_id("tenant-a") == "tenant-a"
    with pytest.raises(TenantContextError):
        validate_tenant_id("   ")
    with pytest.raises(TenantContextError):
        validate_tenant_id("x" * 129)

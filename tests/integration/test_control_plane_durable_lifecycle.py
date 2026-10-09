"""Opt-in end-to-end durable Control Plane -> Kernel lifecycle integration test."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import pytest

from ois.control_plane.controller import ControlPlane
from ois.control_plane.lifecycle import OISProductionLifecycle
from ois.control_plane.request import ControlRequest
from ois.control_plane.sqlite_evidence import SQLiteProductionEvidenceLedger
from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.types import InvocationStatus
from ois.persistence import (
    PostgreSQLCheckpointStore,
    RedisIdempotencyStore,
    RedisTransientCoordinator,
)
from ois.registries.capability_registry import CapabilityRegistry
from production.control_plane import AuthorizationError


class CountingCapability:
    contract = CapabilityContract(
        capability_id="test.durable.echo",
        version="1.0.0",
        description="Deterministic capability for durable lifecycle verification",
    )

    def __init__(self, calls: list[dict[str, object]]) -> None:
        self.calls = calls

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        self.calls.append(dict(request.input))
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"echo": dict(request.input)},
        )


def _lifecycle(
    calls: list[dict[str, object]],
    *,
    postgres_url: str,
    redis_url: str,
    evidence_path: Path,
) -> tuple[OISProductionLifecycle, PostgreSQLCheckpointStore, RedisTransientCoordinator]:
    checkpoints = PostgreSQLCheckpointStore(postgres_url)
    checkpoints.initialize()
    coordinator = RedisTransientCoordinator(redis_url)
    assert coordinator.ping()
    registry = CapabilityRegistry()
    registry.register("test.durable.echo", "1.0.0", CountingCapability(calls))
    evidence = SQLiteProductionEvidenceLedger(str(evidence_path))
    lifecycle = OISProductionLifecycle(
        ControlPlane(capabilities=registry),
        registry,
        checkpoints=checkpoints,
        evidence=evidence,  # type: ignore[arg-type]
        idempotency=RedisIdempotencyStore(coordinator),
    )
    return lifecycle, checkpoints, coordinator


def _execute(
    lifecycle: OISProductionLifecycle,
    *,
    tenant_id: str,
    invocation_id: str,
    input_data: dict[str, object],
    permissions: frozenset[str],
):
    return lifecycle.execute(
        ControlRequest("test.durable.echo", "1.0.0", input_data),
        objective="verify durable Control Plane to Kernel execution",
        tenant_id=tenant_id,
        invocation_id=invocation_id,
        subject_id=f"operator-{tenant_id}",
        permissions=permissions,
        environment="staging",
        attributes={"environment": "staging"},
    )


@pytest.mark.integration
@pytest.mark.live
def test_control_plane_durable_lifecycle_replay_and_tenant_denial(tmp_path: Path) -> None:
    """Persist execution, restart adapters, replay once, and deny a cross-tenant caller."""
    if os.getenv("OIS_LIVE_DURABLE_LIFECYCLE", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        pytest.skip("Set OIS_LIVE_DURABLE_LIFECYCLE=1 to enable durable lifecycle integration")

    postgres_url = os.getenv("OIS_DATABASE_URL")
    redis_url = os.getenv("OIS_REDIS_URL")
    if not postgres_url or not redis_url:
        pytest.skip("OIS_DATABASE_URL and OIS_REDIS_URL are required")

    evidence_path = tmp_path / "control-plane-durable-evidence.sqlite3"
    calls: list[dict[str, object]] = []
    invocation_id = "durable-lifecycle-cross-runtime-replay"
    first_lifecycle, first_checkpoints, first_redis = _lifecycle(
        calls,
        postgres_url=postgres_url,
        redis_url=redis_url,
        evidence_path=evidence_path,
    )
    first_evidence = first_lifecycle.evidence

    try:
        first = _execute(
            first_lifecycle,
            tenant_id="tenant-alpha",
            invocation_id=invocation_id,
            input_data={"value": "persist-this-result"},
            permissions=frozenset({"execution.invoke"}),
        )
        assert first.result.status is InvocationStatus.SUCCEEDED
        assert first.result.output == {"echo": {"value": "persist-this-result"}}
        assert calls == [{"value": "persist-this-result"}]
        assert first_checkpoints.load(UUID(first.execution_id)).identity.tenant_id == "tenant-alpha"
        assert first_checkpoints.load(UUID(first.execution_id)).identity.execution_id == UUID(
            first.execution_id
        )
    finally:
        first_evidence.close()
        first_redis.client.close()

    # Construct a new lifecycle/runtime and reopen all external persistence adapters.
    second_lifecycle, second_checkpoints, second_redis = _lifecycle(
        calls,
        postgres_url=postgres_url,
        redis_url=redis_url,
        evidence_path=evidence_path,
    )
    evidence = second_lifecycle.evidence

    try:
        replay = _execute(
            second_lifecycle,
            tenant_id="tenant-alpha",
            invocation_id=invocation_id,
            input_data={"value": "changed-input-must-not-run"},
            permissions=frozenset({"execution.invoke"}),
        )
        assert replay.result.status is InvocationStatus.SUCCEEDED
        assert replay.result.output == first.result.output
        assert calls == [{"value": "persist-this-result"}], (
            "Capability executed again instead of returning the durable idempotency result"
        )

        with pytest.raises(AuthorizationError, match="permission is missing"):
            _execute(
                second_lifecycle,
                tenant_id="tenant-beta",
                invocation_id=invocation_id,
                input_data={"value": "cross-tenant-must-not-run"},
                permissions=frozenset(),
            )
        assert calls == [{"value": "persist-this-result"}], (
            "Unauthorized cross-tenant request reached the capability"
        )

        events = evidence.events()
        event_types = [event.event_type for event in events]
        assert "control_plane.request.accepted" in event_types
        assert "execution.received" in event_types
        assert "execution.authorized" in event_types
        assert "capability.completed" in event_types
        assert "execution.checkpointed" in event_types
        assert "execution.idempotency_hit" in event_types
        assert "execution.authorization_denied" in event_types
        assert evidence.verify_chain()

        # Reopen the ledger once more to prove evidence durability is not process-local.
        evidence.close()
        reopened_evidence = SQLiteProductionEvidenceLedger(str(evidence_path))
        try:
            reopened_types = [event.event_type for event in reopened_evidence.events()]
            assert "capability.completed" in reopened_types
            assert "execution.idempotency_hit" in reopened_types
            assert "execution.authorization_denied" in reopened_types
            assert reopened_evidence.verify_chain()
        finally:
            reopened_evidence.close()
    finally:
        # Evidence may already be closed above; closing a SQLite connection twice is avoided.
        second_redis.client.close()

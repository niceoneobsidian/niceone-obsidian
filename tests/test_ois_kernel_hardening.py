import asyncio
import hashlib
import hmac
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from production.ois_production_kernel import (
    EvidenceVerificationFailure,
    FencedLease,
    OISProductionSupervisor,
    PermissionDenied,
    SafetyViolation,
    StateRecoveryFailure,
    ToolExecutionFailure,
    TransientKernelFailure,
)

SECRET = b"test-only-secret"
TENANT = "4a2b2520-cb96-48eb-b12e-1e479aaef232"


def supervisor_with_fetchone(row: Any) -> OISProductionSupervisor:
    cursor = MagicMock()
    cursor.execute = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=row)
    conn = MagicMock()
    conn.cursor.return_value.__aenter__ = AsyncMock(return_value=cursor)
    pool = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    return OISProductionSupervisor(pool, AsyncMock(), SECRET)


def test_unsigned_artifact_is_rejected() -> None:
    supervisor = supervisor_with_fetchone(None)
    with pytest.raises(EvidenceVerificationFailure):
        asyncio.run(supervisor.verify_artifact_promotion_gate(TENANT, "flow", "v1"))


def test_signature_is_tenant_bound() -> None:
    manifest = {"routing_dag": []}
    provenance = OISProductionSupervisor.canonical_manifest_hash(manifest)
    supervisor_hash = provenance
    wrong = hmac.new(
        SECRET,
        f"other:flow:v1:{provenance}".encode(),
        hashlib.sha256,
    ).hexdigest()
    supervisor = supervisor_with_fetchone((manifest, supervisor_hash, wrong))

    with pytest.raises(EvidenceVerificationFailure):
        asyncio.run(supervisor.verify_artifact_promotion_gate(TENANT, "flow", "v1"))


def test_manifest_provenance_hash_must_match_payload() -> None:
    manifest = {"routing_dag": []}
    incorrect_provenance = hashlib.sha256(b"different-manifest").hexdigest()
    signature = hmac.new(
        SECRET,
        f"{TENANT}:flow:v1:{incorrect_provenance}".encode(),
        hashlib.sha256,
    ).hexdigest()
    supervisor = supervisor_with_fetchone((manifest, incorrect_provenance, signature))

    with pytest.raises(EvidenceVerificationFailure, match="manifest"):
        asyncio.run(
            supervisor.verify_artifact_promotion_gate(
                TENANT,
                "flow",
                "v1",
            )
        )


def test_valid_manifest_provenance_and_signature_are_accepted() -> None:
    manifest = {"routing_dag": ["evaluate_step", "apply_step"]}
    provenance = OISProductionSupervisor.canonical_manifest_hash(manifest)
    signature = hmac.new(
        SECRET,
        f"{TENANT}:flow:v1:{provenance}".encode(),
        hashlib.sha256,
    ).hexdigest()
    supervisor = supervisor_with_fetchone((manifest, provenance, signature))

    assert (
        asyncio.run(
            supervisor.verify_artifact_promotion_gate(
                TENANT,
                "flow",
                "v1",
            )
        )
        == manifest
    )


def test_lease_release_before_acquire_is_safe() -> None:
    client = AsyncMock()
    lease = FencedLease(client, "lease:test")

    asyncio.run(lease.release())

    client.eval.assert_not_awaited()


@pytest.mark.parametrize(
    ("exception", "scenario"),
    [
        (TransientKernelFailure(), "RC-01"),
        (ToolExecutionFailure(), "RC-03"),
        (ValueError("bad input"), "RC-04"),
        (StateRecoveryFailure(), "RC-06"),
        (Exception("unknown"), "RC-09"),
        (SafetyViolation(), "RC-11"),
        (PermissionDenied(), "RC-12"),
        (EvidenceVerificationFailure(), "RC-12"),
    ],
)
def test_failure_classifier_is_explicit(exception: Exception, scenario: str) -> None:
    assert OISProductionSupervisor.classify_failure(exception) == scenario

import hashlib
import hmac
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


def supervisor_with_fetchone(row):
    cursor = AsyncMock()
    cursor.fetchone.return_value = row
    conn = AsyncMock()
    conn.cursor.return_value.__aenter__.return_value = cursor
    pool = MagicMock()
    pool.connection.return_value.__aenter__.return_value = conn
    return OISProductionSupervisor(pool, AsyncMock(), SECRET)


@pytest.mark.asyncio
async def test_unsigned_artifact_is_rejected():
    supervisor = supervisor_with_fetchone(None)
    with pytest.raises(EvidenceVerificationFailure):
        await supervisor.verify_artifact_promotion_gate(TENANT, "flow", "v1")


@pytest.mark.asyncio
async def test_signature_is_tenant_bound():
    manifest = {"routing_dag": []}
    provenance = supervisor_hash = OISProductionSupervisor.canonical_manifest_hash(manifest)
    wrong = hmac.new(
        SECRET,
        f"other:flow:v1:{provenance}".encode(),
        hashlib.sha256,
    ).hexdigest()
    supervisor = supervisor_with_fetchone((manifest, supervisor_hash, wrong))

    with pytest.raises(EvidenceVerificationFailure):
        await supervisor.verify_artifact_promotion_gate(TENANT, "flow", "v1")


@pytest.mark.asyncio
async def test_manifest_provenance_hash_must_match_payload():
    manifest = {"routing_dag": []}
    incorrect_provenance = hashlib.sha256(b"different-manifest").hexdigest()
    signature = hmac.new(
        SECRET,
        f"{TENANT}:flow:v1:{incorrect_provenance}".encode(),
        hashlib.sha256,
    ).hexdigest()
    supervisor = supervisor_with_fetchone(
        (manifest, incorrect_provenance, signature)
    )

    with pytest.raises(EvidenceVerificationFailure, match="manifest"):
        await supervisor.verify_artifact_promotion_gate(
            TENANT,
            "flow",
            "v1",
        )


@pytest.mark.asyncio
async def test_valid_manifest_provenance_and_signature_are_accepted():
    manifest = {"routing_dag": ["evaluate_step", "apply_step"]}
    provenance = OISProductionSupervisor.canonical_manifest_hash(manifest)
    signature = hmac.new(
        SECRET,
        f"{TENANT}:flow:v1:{provenance}".encode(),
        hashlib.sha256,
    ).hexdigest()
    supervisor = supervisor_with_fetchone((manifest, provenance, signature))

    assert await supervisor.verify_artifact_promotion_gate(
        TENANT,
        "flow",
        "v1",
    ) == manifest


@pytest.mark.asyncio
async def test_lease_release_before_acquire_is_safe():
    client = AsyncMock()
    lease = FencedLease(client, "lease:test")

    await lease.release()

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
def test_failure_classifier_is_explicit(exception, scenario):
    assert OISProductionSupervisor.classify_failure(exception) == scenario

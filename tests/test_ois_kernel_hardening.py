import hashlib
import hmac
import pytest
from unittest.mock import AsyncMock, MagicMock

from production.ois_production_kernel import EvidenceVerificationFailure, OISProductionSupervisor

SECRET = b'test-only-secret'
TENANT = '4a2b2520-cb96-48eb-b12e-1e479aaef232'


def supervisor_with_fetchone(row):
    cursor = AsyncMock(); cursor.fetchone.return_value = row
    conn = AsyncMock(); conn.cursor.return_value.__aenter__.return_value = cursor
    pool = MagicMock(); pool.connection.return_value.__aenter__.return_value = conn
    return OISProductionSupervisor(pool, AsyncMock(), SECRET)

@pytest.mark.asyncio
async def test_unsigned_artifact_is_rejected():
    supervisor = supervisor_with_fetchone(None)
    with pytest.raises(EvidenceVerificationFailure):
        await supervisor.verify_artifact_promotion_gate(TENANT, 'flow', 'v1')

@pytest.mark.asyncio
async def test_signature_is_tenant_bound():
    provenance = hashlib.sha256(b'manifest').hexdigest()
    wrong = hmac.new(SECRET, f'other:flow:v1:{provenance}'.encode(), hashlib.sha256).hexdigest()
    supervisor = supervisor_with_fetchone(({'routing_dag': []}, provenance, wrong))
    with pytest.raises(EvidenceVerificationFailure):
        await supervisor.verify_artifact_promotion_gate(TENANT, 'flow', 'v1')

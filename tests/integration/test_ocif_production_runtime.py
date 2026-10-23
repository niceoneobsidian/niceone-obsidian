from __future__ import annotations

import os
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest

from ois.integration.ocif_import import register_ocif_import_capability
from ois.integration.spine import OISSpine, SpineRequest
from ois.kernel.policy import DefaultPolicyEngine
from ois.kernel.postgres import PostgresDurableExecutionStore
from ois.kernel.postgres_stores import PostgresEvidenceLedger, PostgresIdempotencyStore
from ois.registries import CapabilityRegistry
from production.ocif_runtime import build_ocif_production_runtime

PostgresOCIFStore = pytest.importorskip("ocif.postgres_store").PostgresOCIFStore


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OIS_TEST_POSTGRES_DSN"),
    reason="PostgreSQL integration DSN not configured",
)
def test_real_ocif_consumer_authorization_and_restart_replay() -> None:
    dsn = os.environ["OIS_TEST_POSTGRES_DSN"]
    tenant_id = f"ocif-test-{uuid4()}"
    source_id, capture_id = str(uuid4()), str(uuid4())
    invocation_id = f"ocif-restart-{uuid4()}"
    payload = {
        "contract_version": "0.1.0",
        "source_id": source_id,
        "capture_id": capture_id,
        "submitted_url": "https://example.org/ois-integration",
        "normalized_url": "https://example.org/ois-integration",
        "capture_status": "partial",
        "captured_at": "2026-10-22T10:00:00+00:00",
        "completed_at": "2026-10-22T10:00:01+00:00",
        "artifacts": [],
        "extraction": None,
        "producer_revision": "ois-postgres-integration-test",
        "warnings": [],
    }
    consumer_one = PostgresOCIFStore(dsn)
    consumer_one.initialize()

    def connect() -> Any:
        return psycopg.connect(dsn)

    denied_registry = CapabilityRegistry()
    register_ocif_import_capability(
        denied_registry,
        lambda envelope, stable_id: consumer_one.import_payload(envelope),
    )
    denied_checkpoints = PostgresDurableExecutionStore(dsn, tenant_id=tenant_id)
    denied_idempotency = PostgresIdempotencyStore(connect)
    denied_evidence = PostgresEvidenceLedger(connect)
    denied_checkpoints.initialize()
    denied_idempotency.initialize()
    denied_evidence.initialize()
    denied_spine = OISSpine(
        denied_registry,
        checkpoint_store=denied_checkpoints,
        idempotency=denied_idempotency,
        evidence=denied_evidence,
        policy=DefaultPolicyEngine(allowed_permissions=()),
    )
    request = SpineRequest(
        objective="Import verified evidence",
        capability_id="ocif.import.consume",
        capability_version="1.0.0",
        tenant_id=tenant_id,
        input={"payload": payload},
    )
    denied = denied_spine.submit(request, invocation_id=f"denied-{uuid4()}")
    assert denied.status == "denied"
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM ocif_observations WHERE source_id=%s AND capture_id=%s",
            (source_id, capture_id),
        )
        assert cursor.fetchone()[0] == 0

    permissions = ("ocif.evidence.import",)
    runtime_one = build_ocif_production_runtime(
        postgres_dsn=dsn,
        tenant_id=tenant_id,
        consumer=consumer_one,
        allowed_permissions=permissions,
    )
    first = runtime_one.spine.submit(request, invocation_id=invocation_id)
    assert first.status == "succeeded"
    assert first.output["status"] == "accepted"
    recovered_checkpoint = runtime_one.spine.checkpoints.fetch_last_valid_checkpoint(
        UUID(first.execution_id),
        tenant_id=tenant_id,
    )
    assert recovered_checkpoint is not None
    assert recovered_checkpoint.identity.tenant_id == tenant_id

    # Rebuild every OIS store and the consumer as if the worker process restarted.
    consumer_two = PostgresOCIFStore(dsn)
    consumer_two.initialize()
    runtime_two = build_ocif_production_runtime(
        postgres_dsn=dsn,
        tenant_id=tenant_id,
        consumer=consumer_two,
        allowed_permissions=permissions,
    )
    replay = runtime_two.spine.submit(request, invocation_id=invocation_id)
    assert replay.status == "succeeded"
    assert replay.output["observation_id"] == first.output["observation_id"]

    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM ocif_observations WHERE source_id=%s AND capture_id=%s",
            (source_id, capture_id),
        )
        assert cursor.fetchone()[0] == 1

    consumer_one.close()
    consumer_two.close()

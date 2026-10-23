from __future__ import annotations

import os
from uuid import uuid4

import pytest

PostgresOCIFStore = pytest.importorskip("ocif.postgres_store").PostgresOCIFStore

from ois.integration.spine import SpineRequest
from production.ocif_runtime import build_ocif_production_runtime


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OIS_TEST_POSTGRES_DSN"),
    reason="PostgreSQL integration DSN not configured",
)
def test_real_ocif_consumer_replay_survives_ois_runtime_restart() -> None:
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
    permissions = ("ocif.evidence.import",)
    consumer_one = PostgresOCIFStore(dsn)
    consumer_one.initialize()
    runtime_one = build_ocif_production_runtime(
        postgres_dsn=dsn, tenant_id=tenant_id, consumer=consumer_one,
        allowed_permissions=permissions,
    )
    request = SpineRequest(
        objective="Import verified evidence",
        capability_id="ocif.import.consume",
        capability_version="1.0.0",
        tenant_id=tenant_id,
        input={"payload": payload},
    )
    first = runtime_one.spine.submit(request, invocation_id=invocation_id)
    assert first.status == "succeeded"
    assert first.output["status"] == "accepted"

    # Rebuild every OIS store and the consumer as if the worker process restarted.
    consumer_two = PostgresOCIFStore(dsn)
    consumer_two.initialize()
    runtime_two = build_ocif_production_runtime(
        postgres_dsn=dsn, tenant_id=tenant_id, consumer=consumer_two,
        allowed_permissions=permissions,
    )
    replay = runtime_two.spine.submit(request, invocation_id=invocation_id)
    assert replay.status == "succeeded"
    assert replay.output["observation_id"] == first.output["observation_id"]

    import psycopg

    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM ocif_observations WHERE source_id=%s AND capture_id=%s",
            (source_id, capture_id),
        )
        assert cursor.fetchone()[0] == 1

    consumer_one.close()
    consumer_two.close()

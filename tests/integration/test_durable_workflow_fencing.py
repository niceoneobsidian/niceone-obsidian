from __future__ import annotations

from uuid import UUID

import psycopg
import pytest

from ois.autonomy.durable import (
    DurableRunStatus,
    DurableWorkflowRun,
    FencedPostgresWorkflowRunRepository,
    PostgresWorkflowRunRepository,
)
from ois.infrastructure.postgres_fencing import FencingError, PostgresWorkerLeaseStore

RUN_ID = UUID("00000000-0000-0000-0000-000000000193")


def test_stale_worker_cannot_transition_workflow_run(migrated_postgres: str) -> None:
    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM autonomous_workflow_runs WHERE run_id = %s", (RUN_ID,))
        cursor.execute("DELETE FROM ois_worker_leases WHERE execution_id = %s", (RUN_ID,))
        cursor.execute(
            """INSERT INTO autonomous_workflow_runs
            (run_id, tenant_id, workspace_id, workflow_id, workflow_version, event_id, status)
            VALUES (%s, 'tenant', 'workspace', 'workflow', '1', 'event-193', 'received')""",
            (RUN_ID,),
        )

    leases = PostgresWorkerLeaseStore(lambda: psycopg.connect(migrated_postgres), ttl_seconds=30)
    stale = leases.claim(RUN_ID, "worker-a")
    assert stale is not None

    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE ois_worker_leases SET lease_expires_at = now() - interval '1 second' "
            "WHERE execution_id = %s",
            (RUN_ID,),
        )

    current = leases.claim(RUN_ID, "worker-b")
    assert current is not None
    repo = PostgresWorkflowRunRepository(lambda: psycopg.connect(migrated_postgres))
    fenced = FencedPostgresWorkflowRunRepository(repo, leases, stale)

    with pytest.raises(FencingError):
        fenced.transition(RUN_ID, status=DurableRunStatus.RUNNING)

    current_repo = FencedPostgresWorkflowRunRepository(repo, leases, current)
    updated = current_repo.transition(RUN_ID, status=DurableRunStatus.RUNNING)
    assert updated.status == DurableRunStatus.RUNNING

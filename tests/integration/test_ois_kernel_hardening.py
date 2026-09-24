from __future__ import annotations

import asyncio

import psycopg
from psycopg_pool import AsyncConnectionPool
import pytest

from production.ois_production_kernel import EvidenceLedger


TENANT = "4a2b2520-cb96-48eb-b12e-1e479aaef232"


@pytest.mark.integration
def test_concurrent_evidence_appends_are_serialized(
    migrated_postgres: str,
) -> None:
    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM ois_attestation_evidence WHERE tenant_id = %s",
            (TENANT,),
        )
        connection.commit()

    async def append_concurrently() -> None:
        pool = AsyncConnectionPool(
            conninfo=migrated_postgres,
            min_size=1,
            max_size=4,
            open=False,
        )
        await pool.open()
        try:
            ledger = EvidenceLedger(pool, b"integration-secret")
            await asyncio.gather(
                ledger.append(
                    TENANT,
                    "thread-1",
                    "EVENT_A",
                    "a" * 64,
                    {"value": "a"},
                ),
                ledger.append(
                    TENANT,
                    "thread-1",
                    "EVENT_B",
                    "b" * 64,
                    {"value": "b"},
                ),
            )
        finally:
            await pool.close()

    asyncio.run(append_concurrently())

    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT sequence_no, previous_hash, event_hash
            FROM ois_attestation_evidence
            WHERE tenant_id = %s AND thread_id = %s
            ORDER BY sequence_no
            """,
            (TENANT, "thread-1"),
        )
        rows = cursor.fetchall()

    assert [row[0] for row in rows] == [1, 2]
    assert rows[0][1] == "0" * 64
    assert rows[1][1] == rows[0][2]


@pytest.mark.integration
def test_kernel_rls_policies_include_write_checks(
    migrated_postgres: str,
) -> None:
    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tablename, policyname, cmd, with_check
            FROM pg_policies
            WHERE tablename IN (
                'ois_graph_state_store',
                'ois_attestation_evidence',
                'ois_kernel_dead_letter_queue',
                'ois_artifact_registry'
            )
            ORDER BY tablename, policyname
            """
        )
        policies = cursor.fetchall()

    policy_map = {
        (row[0], row[1]): (row[2], row[3])
        for row in policies
    }
    assert policy_map[
        ("ois_artifact_registry", "tenant_registry_insert")
    ][0] == "INSERT"
    assert policy_map[
        ("ois_artifact_registry", "tenant_registry_insert")
    ][1] is not None
    assert policy_map[
        ("ois_graph_state_store", "tenant_state_update")
    ][0] == "UPDATE"
    assert policy_map[
        ("ois_graph_state_store", "tenant_state_update")
    ][1] is not None

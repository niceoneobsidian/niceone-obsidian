from __future__ import annotations

import asyncio

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from production.ois_production_kernel import EvidenceLedger


TENANT = "4a2b2520-cb96-48eb-b12e-1e479aaef232"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_evidence_appends_are_serialized(
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


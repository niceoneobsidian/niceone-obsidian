from __future__ import annotations

import os

import pytest
import pytest_asyncio
from psycopg import errors
from psycopg_pool import AsyncConnectionPool

from ois.integration.postgres_pool import create_tenant_pool
from ois.kernel.tenant import set_local_tenant

DB_DSN = os.getenv("OIS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> AsyncConnectionPool:
    if not DB_DSN:
        pytest.skip("OIS_TEST_DATABASE_URL is required for PostgreSQL integration tests")
    pool = create_tenant_pool(DB_DSN, open=False, min_size=1, max_size=4)
    await pool.open()
    try:
        async with pool.connection() as conn:
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS ois_rls_adversarial_fixture "
                "(id text PRIMARY KEY, tenant_id uuid NOT NULL, secret text NOT NULL)"
            )
            await conn.execute("ALTER TABLE ois_rls_adversarial_fixture ENABLE ROW LEVEL SECURITY")
            await conn.execute("ALTER TABLE ois_rls_adversarial_fixture FORCE ROW LEVEL SECURITY")
            await conn.execute("DROP POLICY IF EXISTS tenant_isolation ON ois_rls_adversarial_fixture")
            await conn.execute(
                "CREATE POLICY tenant_isolation ON ois_rls_adversarial_fixture "
                "USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid) "
                "WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)"
            )
            await conn.execute("TRUNCATE ois_rls_adversarial_fixture")
            await conn.execute(
                "INSERT INTO ois_rls_adversarial_fixture (id, tenant_id, secret) "
                "VALUES (%s, %s, %s), (%s, %s, %s)",
                (
                    "tenant-a-record", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "A-secret",
                    "tenant-b-record", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "B-secret",
                ),
            )
            await conn.commit()
        yield pool
    finally:
        async with pool.connection() as conn:
            await conn.execute("DROP TABLE IF EXISTS ois_rls_adversarial_fixture")
            await conn.commit()
        await pool.close()


async def test_cross_tenant_read_isolation(pool: AsyncConnectionPool) -> None:
    async with pool.connection() as conn:
        set_local_tenant(conn, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        row = await conn.execute(
            "SELECT secret FROM ois_rls_adversarial_fixture WHERE id = %s",
            ("tenant-b-record",),
        )
        assert await row.fetchone() is None
        await conn.rollback()


async def test_parameterized_identifier_cannot_escape_query(pool: AsyncConnectionPool) -> None:
    payload = "tenant-a-record' OR tenant_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    async with pool.connection() as conn:
        set_local_tenant(conn, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        row = await conn.execute(
            "SELECT id FROM ois_rls_adversarial_fixture WHERE id = %s",
            (payload,),
        )
        assert await row.fetchall() == []
        await conn.rollback()


async def test_pool_reset_removes_sticky_tenant_context(pool: AsyncConnectionPool) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "SELECT set_config('app.current_tenant_id', %s, false)",
            ("66666666-6666-6666-6666-666666666666",),
        )
        await conn.commit()

    async with pool.connection() as conn:
        row = await conn.execute("SELECT current_setting('app.current_tenant_id', true)")
        value = (await row.fetchone())[0]
        assert value != "66666666-6666-6666-6666-666666666666"
        await conn.rollback()


async def test_cross_tenant_write_is_rejected(pool: AsyncConnectionPool) -> None:
    async with pool.connection() as conn:
        set_local_tenant(conn, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        with pytest.raises(errors.InsufficientPrivilege):
            await conn.execute(
                "INSERT INTO ois_rls_adversarial_fixture (id, tenant_id, secret) VALUES (%s, %s, %s)",
                ("forbidden", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "leak"),
            )
        await conn.rollback()

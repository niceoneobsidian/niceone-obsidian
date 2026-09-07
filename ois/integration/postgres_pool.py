from __future__ import annotations

from typing import Any

from psycopg_pool import AsyncConnectionPool

from ois.kernel.tenant import normalize_tenant_id, set_local_tenant


async def reset_connection(connection: Any) -> None:
    """Remove transaction/session state before a connection re-enters the pool."""
    await connection.rollback()
    await connection.execute("RESET ALL")
    await connection.execute("DISCARD TEMP")


def create_tenant_pool(dsn: str, **kwargs: Any) -> AsyncConnectionPool:
    """Create an OIS pool whose reset hook prevents sticky tenant context."""
    return AsyncConnectionPool(dsn, reset=reset_connection, **kwargs)


async def bind_tenant(connection: Any, tenant_id: str) -> str:
    """Bind a validated tenant to the current transaction; caller owns commit/rollback."""
    normalized = normalize_tenant_id(tenant_id)
    set_local_tenant(connection, normalized)
    return normalized

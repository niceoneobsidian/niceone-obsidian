from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
from uuid import UUID


class TenantContextError(ValueError):
    """Raised when tenant context is missing or malformed."""


def normalize_tenant_id(tenant_id: str | UUID) -> str:
    try:
        return str(UUID(str(tenant_id)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise TenantContextError("tenant_id must be a valid UUID") from exc


def set_local_tenant(connection: Any, tenant_id: str | UUID) -> None:
    """Set PostgreSQL tenant context using a parameterized, transaction-local GUC."""
    normalized = normalize_tenant_id(tenant_id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.current_tenant_id', %s, true)", (normalized,))


@contextmanager
def tenant_transaction(connection: Any, tenant_id: str | UUID) -> Iterator[Any]:
    """Bind tenant identity for exactly one PostgreSQL transaction."""
    set_local_tenant(connection, tenant_id)
    yield connection

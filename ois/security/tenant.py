from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


class TenantContextError(ValueError):
    """Raised when a tenant context is missing or malformed."""


def validate_tenant_id(tenant_id: str) -> str:
    value = tenant_id.strip()
    if not value:
        raise TenantContextError("tenant_id is required")
    if len(value) > 128:
        raise TenantContextError("tenant_id exceeds the supported length")
    return value


@contextmanager
def postgres_tenant_context(connection: Any, tenant_id: str) -> Iterator[Any]:
    """Bind tenant identity to the current transaction without SQL interpolation.

    The caller owns transaction commit/rollback. ``SET LOCAL`` semantics are
    intentionally scoped to the current transaction and therefore cannot leak
    tenant context across pooled connections.
    """
    validated = validate_tenant_id(tenant_id)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.current_tenant_id', %s, true)",
            (validated,),
        )
    yield connection

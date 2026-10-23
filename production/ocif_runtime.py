"""Production composition for the governed OIS -> OCIF import path.

Install OCIF with its postgres extra and pass a durable ocif.PostgresOCIFStore.
OIS checkpoints, idempotency and evidence plus OCIF observations/quarantine/events
then use PostgreSQL. The SQLite OCIFStore remains the local reference consumer.
The existing OIS evidence/idempotency tables still require a reviewed tenant-isolation
migration and live conformance review before this composition is approved for multi-tenant
production; this factory is a production-shaped composition, not a deployment attestation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import psycopg

from ois.integration.ocif_import import register_ocif_import_capability
from ois.integration.spine import OISSpine
from ois.kernel.policy import DefaultPolicyEngine
from ois.kernel.postgres import PostgresDurableExecutionStore
from ois.kernel.postgres_stores import PostgresEvidenceLedger, PostgresIdempotencyStore
from ois.kernel.recovery import RecoveryPolicy
from ois.registries import CapabilityRegistry


class OCIFConsumer(Protocol):
    """Minimum interface implemented by OCIFStore and PostgresOCIFStore."""

    def import_payload(self, payload: Any) -> Any: ...


@dataclass(frozen=True)
class OCIFProductionRuntime:
    """Composed governed spine and the exact OCIF store instance it writes to."""

    spine: OISSpine
    consumer: OCIFConsumer


def build_ocif_production_runtime(
    *,
    postgres_dsn: str,
    tenant_id: str,
    consumer: OCIFConsumer,
    allowed_permissions: tuple[str, ...] = (),
    connection_factory: Callable[[], Any] | None = None,
) -> OCIFProductionRuntime:
    """Build a PostgreSQL-durable OIS spine around the real OCIF consumer.

    The caller must explicitly grant ocif.evidence.import and pass a durable
    PostgresOCIFStore for a shared runtime. No in-memory OIS store is selected here.
    Tenant isolation of OIS evidence/idempotency tables remains a separate release gate.
    """
    if not postgres_dsn.strip():
        raise ValueError("postgres_dsn is required")
    if not tenant_id.strip():
        raise ValueError("tenant_id is required")
    if "ocif.evidence.import" not in allowed_permissions:
        raise PermissionError(
            "production composition requires explicit ocif.evidence.import permission"
        )

    connect = connection_factory or (lambda: psycopg.connect(postgres_dsn))
    checkpoints = PostgresDurableExecutionStore(postgres_dsn, tenant_id=tenant_id)
    idempotency = PostgresIdempotencyStore(connect)
    evidence = PostgresEvidenceLedger(connect)

    # Fail during startup, not on the first production request.
    checkpoints.initialize()
    idempotency.initialize()
    evidence.initialize()

    registry = CapabilityRegistry()
    register_ocif_import_capability(
        registry,
        lambda payload, invocation_id: consumer.import_payload(payload),
    )
    spine = OISSpine(
        registry,
        checkpoint_store=checkpoints,
        evidence=evidence,
        idempotency=idempotency,
        recovery=RecoveryPolicy(max_retries=2, max_recovery_attempts=3),
        policy=DefaultPolicyEngine(allowed_permissions=allowed_permissions),
    )
    return OCIFProductionRuntime(spine=spine, consumer=consumer)

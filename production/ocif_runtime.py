"""Production composition for the governed OIS -> OCIF import path.

Install the OCIF consumer package in the same runtime and pass its real OCIFStore.
OIS execution, idempotency and evidence state use PostgreSQL. The current OCIFStore
implementation is SQLite-backed; therefore this factory is suitable for controlled
single-consumer deployments, not a horizontally scaled OCIF writer until OCIF ships
a PostgreSQL consumer store.
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
    """Minimum interface implemented by the real OCIF ingestion.OCIFStore."""

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

    The caller must explicitly grant ocif.evidence.import. The supplied OCIF
    store must itself use durable storage. No in-memory OIS store is selected here.
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

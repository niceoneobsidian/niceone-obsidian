"""Reusable PostgreSQL-durable OIS runtime composition for one tenant scope."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import psycopg

from ois.integration.spine import OISSpine
from ois.kernel.policy import DefaultPolicyEngine, PolicyEngine
from ois.kernel.postgres import PostgresDurableExecutionStore
from ois.kernel.postgres_stores import PostgresEvidenceLedger, PostgresIdempotencyStore
from ois.kernel.recovery import RecoveryPolicy
from ois.registries import CapabilityRegistry


@dataclass
class DurableOISRuntime:
    """A composed OIS spine and its durable PostgreSQL stores."""

    spine: OISSpine
    checkpoints: PostgresDurableExecutionStore
    idempotency: PostgresIdempotencyStore
    evidence: PostgresEvidenceLedger

    def close(self) -> None:
        """Release adapters that expose explicit close methods."""
        for store in (self.checkpoints, self.idempotency, self.evidence):
            close = getattr(store, "close", None)
            if callable(close):
                close()


def build_durable_ois_runtime(
    registry: CapabilityRegistry,
    *,
    postgres_dsn: str,
    tenant_id: str,
    policy: PolicyEngine | None = None,
    allowed_permissions: tuple[str, ...] = (),
    connection_factory: Callable[[], Any] | None = None,
) -> DurableOISRuntime:
    """Build a tenant-scoped OIS spine; initialize all durable stores before returning."""
    if not postgres_dsn.strip():
        raise ValueError("postgres_dsn is required")
    if not tenant_id.strip():
        raise ValueError("tenant_id is required")
    connect = connection_factory or (lambda: psycopg.connect(postgres_dsn))
    checkpoints = PostgresDurableExecutionStore(postgres_dsn, tenant_id=tenant_id)
    idempotency = PostgresIdempotencyStore(connect)
    evidence = PostgresEvidenceLedger(connect)
    checkpoints.initialize()
    idempotency.initialize()
    evidence.initialize()
    spine = OISSpine(
        registry,
        checkpoint_store=checkpoints,
        evidence=evidence,
        idempotency=idempotency,
        policy=policy or DefaultPolicyEngine(allowed_permissions=allowed_permissions),
        recovery=RecoveryPolicy(max_retries=2, max_recovery_attempts=3),
    )
    return DurableOISRuntime(spine, checkpoints, idempotency, evidence)

"""Database-enforced fencing helpers for durable side effects."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .postgres import ExecutionLease, LeaseLost


class PostgreSQLSideEffectFencer:
    """Fence side-effect outbox completion against the current worker epoch.

    The adapter deliberately keeps side-effect execution outside the kernel. It
    only controls the durable ownership transition on ``ois_side_effect_outbox``.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL support requires the 'psycopg' package.") from exc
        return psycopg.connect(self._dsn)

    def claim(self, effect_id: str, lease: ExecutionLease) -> bool:
        """Claim a pending effect only while the lease is authoritative."""
        now = datetime.now(UTC)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ois_side_effect_outbox AS effect
                SET status = 'PROCESSING',
                    worker_id = %s,
                    worker_epoch = %s,
                    locked_at = %s,
                    updated_at = %s
                WHERE effect_id = %s
                  AND status = 'PENDING'
                  AND EXISTS (
                      SELECT 1 FROM ois_execution_leases AS lease
                      WHERE lease.execution_id = effect.execution_id
                        AND lease.worker_id = %s
                        AND lease.lease_epoch = %s
                        AND lease.state = 'active'
                        AND lease.expires_at > %s
                  )
                RETURNING effect_id
                """,
                (
                    lease.worker_id, lease.lease_epoch, now, now, effect_id,
                    lease.worker_id, lease.lease_epoch, now,
                ),
            )
            if cursor.fetchone() is None:
                raise LeaseLost(
                    f"fenced side-effect claim rejected for {effect_id} "
                    f"at epoch {lease.lease_epoch}"
                )
        return True

    def complete(self, effect_id: str, lease: ExecutionLease) -> bool:
        """Complete an effect only if the same worker epoch still owns execution."""
        now = datetime.now(UTC)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ois_side_effect_outbox AS effect
                SET status = 'COMPLETED',
                    updated_at = %s
                WHERE effect_id = %s
                  AND status = 'PROCESSING'
                  AND worker_id = %s
                  AND worker_epoch = %s
                  AND EXISTS (
                      SELECT 1 FROM ois_execution_leases AS lease
                      WHERE lease.execution_id = effect.execution_id
                        AND lease.worker_id = %s
                        AND lease.lease_epoch = %s
                        AND lease.state = 'active'
                        AND lease.expires_at > %s
                  )
                RETURNING effect_id
                """,
                (
                    now, effect_id, lease.worker_id, lease.lease_epoch,
                    lease.worker_id, lease.lease_epoch, now,
                ),
            )
            if cursor.fetchone() is None:
                raise LeaseLost(
                    f"fenced side-effect completion rejected for {effect_id} "
                    f"at epoch {lease.lease_epoch}"
                )
        return True

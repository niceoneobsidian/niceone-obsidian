from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ois.kernel.state import ExecutionContext


class CheckpointCorruptionError(RuntimeError):
    """Raised when a stored checkpoint cannot be validated."""


class PostgreSQLCheckpointStore:
    """Append-only PostgreSQL JSONB checkpoint store for OIS execution state.

    The adapter uses psycopg 3, matching the repository's dependency set. Checkpoints
    are immutable rows; recovery walks newest-to-oldest and returns the newest snapshot
    that successfully rehydrates as an ``ExecutionContext``.
    """

    def __init__(self, connection_string: str, *, auto_initialize: bool = False) -> None:
        self.connection_string = connection_string
        if auto_initialize:
            self.initialize()

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection[dict[str, object]]]:
        with psycopg.connect(self.connection_string, row_factory=dict_row) as connection:
            yield connection

    def initialize(self) -> None:
        """Create the checkpoint ledger and immutable-row trigger."""
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ois_workflow_checkpoints (
                        checkpoint_id UUID PRIMARY KEY,
                        execution_id UUID NOT NULL,
                        tenant_id TEXT NOT NULL,
                        step_index INTEGER NOT NULL,
                        state_snapshot JSONB NOT NULL,
                        snapshot_sha256 CHAR(64) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_ois_execution_steps
                    ON ois_workflow_checkpoints (tenant_id, execution_id, step_index DESC, created_at DESC);
                    CREATE OR REPLACE FUNCTION ois_reject_checkpoint_mutation()
                    RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN
                        RAISE EXCEPTION 'OIS checkpoints are immutable';
                    END;
                    $$;
                    DROP TRIGGER IF EXISTS trg_ois_checkpoint_immutable
                    ON ois_workflow_checkpoints;
                    CREATE TRIGGER trg_ois_checkpoint_immutable
                    BEFORE UPDATE OR DELETE ON ois_workflow_checkpoints
                    FOR EACH ROW EXECUTE FUNCTION ois_reject_checkpoint_mutation();
                    """
                )
            connection.commit()

    @staticmethod
    def _canonical_json(payload: Mapping[str, object]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def save_checkpoint(self, checkpoint_id: UUID, state: ExecutionContext) -> None:
        """Persist one immutable, content-addressed checkpoint."""
        payload = state.to_dict()
        canonical = self._canonical_json(payload)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        execution_id = state.identity.execution_id
        step_index = int(state.metadata.get("step_index", state.retry_count))

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ois_workflow_checkpoints
                        (checkpoint_id, execution_id, tenant_id, step_index, state_snapshot, snapshot_sha256)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (checkpoint_id) DO NOTHING;
                    """,
                    (
                        checkpoint_id,
                        execution_id,
                        state.identity.tenant_id,
                        step_index,
                        Jsonb(payload),
                        digest,
                    ),
                )
            connection.commit()

    def fetch_last_valid_checkpoint(
        self, execution_id: UUID, *, tenant_id: str = "default"
    ) -> ExecutionContext | None:
        """Return the newest checksum-valid and schema-valid checkpoint."""
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT checkpoint_id, state_snapshot, snapshot_sha256
                    FROM ois_workflow_checkpoints
                    WHERE tenant_id = %s AND execution_id = %s
                    ORDER BY step_index DESC, created_at DESC
                    """,
                    (tenant_id, execution_id),
                )
                rows = cursor.fetchall()

        for row in rows:
            snapshot = row["state_snapshot"]
            if not isinstance(snapshot, Mapping):
                continue
            canonical = self._canonical_json(snapshot)
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if digest != row["snapshot_sha256"]:
                continue
            try:
                return ExecutionContext.from_dict(snapshot)
            except (TypeError, ValueError, KeyError):
                continue
        return None

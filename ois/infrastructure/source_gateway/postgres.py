"""PostgreSQL production persistence for the Source Gateway and publication ledger.

The database is the durability boundary for the focused Social Intelligence
production path: raw evidence and its outbox event are committed atomically,
while publication attempts are recorded idempotently and never inferred from
in-memory state.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import psycopg

from .evidence import RawEvidence, canonical_hash
from .outbox import OutboxEvent


class PostgresSourceLedger:
    """Atomic raw-evidence/outbox store plus durable publication ledger."""

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection

    def initialize(self) -> None:
        raise RuntimeError("Database schema must be applied through repository migrations")

    def commit_ingest(self, evidence: RawEvidence, event: OutboxEvent) -> bool:
        if canonical_hash(evidence.payload) != evidence.payload_hash:
            raise ValueError("payload_hash does not match canonical payload")
        if (
            evidence.tenant_id != event.tenant_id
            or evidence.workspace_id != event.workspace_id
            or event.aggregate_id != evidence.evidence_id
        ):
            raise PermissionError("evidence and outbox event scopes/aggregate differ")

        with self._connection.transaction(), self._connection.cursor() as cur:
            cur.execute(
            """
            INSERT INTO raw_evidence
            (evidence_id, tenant_id, workspace_id, source_id, source_record_id,
            payload, payload_hash, collected_at, connector_version,
            schema_version, ingestion_run_id)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
            RETURNING evidence_id
            """,
            (
            evidence.evidence_id,
            evidence.tenant_id,
            evidence.workspace_id,
            evidence.source_id,
            evidence.source_record_id,
            json.dumps(evidence.payload, default=str),
            evidence.payload_hash,
            evidence.collected_at,
            evidence.connector_version,
            evidence.schema_version,
            evidence.ingestion_run_id,
            ),
            )
            inserted = cur.fetchone() is not None

            if not inserted:
            cur.execute(
            """
            SELECT evidence_id
            FROM raw_evidence
            WHERE tenant_id=%s AND workspace_id=%s
            AND source_id=%s AND source_record_id=%s
            AND payload_hash=%s
            """,
            (
            evidence.tenant_id,
            evidence.workspace_id,
            evidence.source_id,
            evidence.source_record_id,
            evidence.payload_hash,
            ),
            )
            existing = cur.fetchone()
            if existing is None:
            raise RuntimeError(
            "duplicate evidence was reported but could not be located"
            )
            event = OutboxEvent(
            event_id=event.event_id,
            tenant_id=event.tenant_id,
            workspace_id=event.workspace_id,
            event_type=event.event_type,
            aggregate_id=existing[0],
            payload={**event.payload, "evidence_id": existing[0]},
            created_at=event.created_at,
            )

            cur.execute(
            """
            INSERT INTO source_outbox
            (event_id, tenant_id, workspace_id, event_type, aggregate_id,
            payload, created_at)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
            ON CONFLICT (event_id) DO NOTHING
            """,
            (
            event.event_id,
            event.tenant_id,
            event.workspace_id,
            event.event_type,
            event.aggregate_id,
            json.dumps(event.payload, default=str),
            event.created_at,
            ),
            )
        return True

    def pending(self, *, limit: int = 100) -> tuple[OutboxEvent, ...]:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT event_id, tenant_id, workspace_id, event_type, aggregate_id,
                       payload, created_at
                FROM source_outbox
                WHERE published_at IS NULL
                ORDER BY created_at, event_id
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return tuple(
            OutboxEvent(
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                dict(row[5]),
                row[6],
            )
            for row in rows
        )

    def mark_published(self, event_id: str) -> None:
        with self._connection.transaction(), self._connection.cursor() as cur:
            cur.execute(
            """
            UPDATE source_outbox
            SET published_at = COALESCE(published_at, %s)
            WHERE event_id = %s
            """,
            (datetime.now(UTC), event_id),
            )

    def evidence(
        self,
        evidence_id: str,
        *,
        tenant_id: str,
        workspace_id: str,
    ) -> RawEvidence | None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT evidence_id, tenant_id, workspace_id, source_id, source_record_id,
                       payload, payload_hash, collected_at, connector_version,
                       schema_version, ingestion_run_id
                FROM raw_evidence
                WHERE evidence_id = %s
                  AND tenant_id = %s
                  AND workspace_id = %s
                """,
                (evidence_id, tenant_id, workspace_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        evidence = RawEvidence(*row)
        if canonical_hash(evidence.payload) != evidence.payload_hash:
            raise ValueError("stored raw evidence failed hash verification")
        return evidence

    def record_publication(
        self,
        *,
        publication_id: str,
        event_id: str,
        destination: str,
        idempotency_key: str,
    ) -> bool:
        now = datetime.now(UTC)
        with self._connection.transaction(), self._connection.cursor() as cur:
            cur.execute(
            """
            INSERT INTO publication_ledger
            (publication_id,event_id,destination,idempotency_key,status,attempts,
            created_at,updated_at)
            VALUES (%s,%s,%s,%s,'pending',0,%s,%s)
            ON CONFLICT (destination,idempotency_key) DO NOTHING
            RETURNING publication_id
            """,
            (
            publication_id,
            event_id,
            destination,
            idempotency_key,
            now,
            now,
            ),
            )
            return cur.fetchone() is not None

    def record_publication_attempt(
        self,
        *,
        destination: str,
        idempotency_key: str,
        success: bool,
        error: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        with self._connection.transaction(), self._connection.cursor() as cur:
            cur.execute(
            """
            UPDATE publication_ledger
            SET attempts = attempts + 1,
            status = %s,
            last_error = %s,
            updated_at = %s,
            published_at = CASE WHEN %s THEN %s ELSE published_at END
            WHERE destination = %s AND idempotency_key = %s
            """,
            (
            "published" if success else "failed",
            error,
            now,
            success,
            now,
            destination,
            idempotency_key,
            ),
            )

    def publication(
        self,
        *,
        destination: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT publication_id,event_id,destination,idempotency_key,status,attempts,
                       last_error,created_at,updated_at,published_at
                FROM publication_ledger
                WHERE destination=%s AND idempotency_key=%s
                """,
                (destination, idempotency_key),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return dict(
            zip(
                (
                    "publication_id",
                    "event_id",
                    "destination",
                    "idempotency_key",
                    "status",
                    "attempts",
                    "last_error",
                    "created_at",
                    "updated_at",
                    "published_at",
                ),
                row,
                strict=True,
            )
        )

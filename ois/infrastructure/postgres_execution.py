"""DB-API PostgreSQL adapters for durable state and evidence.

The adapter accepts an existing DB-API connection factory, keeping psycopg optional
for callers and making transaction ownership explicit at the boundary.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Protocol, cast

from ois.application.state import ExecutionState, transition


class Connection(Protocol):
    def cursor(self) -> Any: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class PostgresExecutionStore:
    def __init__(self, connection_factory: Callable[[], Connection]) -> None:
        self._connection_factory = connection_factory

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        connection = self._connection_factory()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            close = getattr(connection, "close", None)
            if close:
                close()

    def append_evidence(self, execution_id: str, category: str, payload: dict[str, Any]) -> None:
        with self.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO execution_evidence "
                "(execution_id, category, payload) "
                "VALUES (%s, %s, %s)",
                (execution_id, category, json.dumps(payload, sort_keys=True)),
            )

    def get_state(self, execution_id: str) -> ExecutionState | None:
        with self.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT state FROM execution_state WHERE execution_id = %s",
                (execution_id,),
            )
            row = cursor.fetchone()
            return ExecutionState(row[0]) if row else None

    def set_state(self, execution_id: str, state: ExecutionState) -> None:
        with self.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT state FROM execution_state WHERE execution_id = %s FOR UPDATE",
                (execution_id,),
            )
            row = cursor.fetchone()
            if row is not None:
                current_state = ExecutionState(row[0])
                transition(current_state, state)
                cursor.execute(
                    "UPDATE execution_state SET state = %s, updated_at = now() "
                    "WHERE execution_id = %s",
                    (state.value, execution_id),
                )
            else:
                cursor.execute(
                    "INSERT INTO execution_state (execution_id, state) VALUES (%s, %s)",
                    (execution_id, state.value),
                )

    def claim_idempotency(
        self,
        invocation_id: str,
        execution_id: str,
        tenant_id: str,
        capability_id: str,
        request_fingerprint: str,
    ) -> bool:
        """Atomically claim an invocation key.

        Returns True for the first claimant and False for a matching replay.
        Reusing a key with a different request fingerprint fails closed.
        """
        with self.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO ois_idempotency_results "
                "(invocation_id, execution_id, tenant_id, capability_id, status, "
                "result, request_fingerprint) "
                "VALUES (%s, %s, %s, %s, 'PENDING', %s, %s) "
                "ON CONFLICT (invocation_id) DO NOTHING "
                "RETURNING invocation_id",
                (
                    invocation_id,
                    execution_id,
                    tenant_id,
                    capability_id,
                    json.dumps({}),
                    request_fingerprint,
                ),
            )
            if cursor.fetchone() is not None:
                return True

            cursor.execute(
                "SELECT request_fingerprint FROM ois_idempotency_results "
                "WHERE invocation_id = %s FOR UPDATE",
                (invocation_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("idempotency claim disappeared during transaction")
            if row[0] != request_fingerprint:
                raise ValueError("idempotency key reused with a different request")
            return False

    def complete_idempotency(self, invocation_id: str, result: dict[str, Any]) -> None:
        with self.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE ois_idempotency_results "
                "SET status = 'COMPLETED', result = %s "
                "WHERE invocation_id = %s AND status = 'PENDING'",
                (json.dumps(result, sort_keys=True), invocation_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown or completed invocation: {invocation_id}")

    def get_idempotency_result(self, invocation_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT status, result FROM ois_idempotency_results WHERE invocation_id = %s",
                (invocation_id,),
            )
            row = cursor.fetchone()
            if row is None or row[0] != "COMPLETED":
                return None
            result = row[1]
            if isinstance(result, str):
                result = json.loads(result)
            return cast(dict[str, Any], result)

    def release_idempotency(self, invocation_id: str) -> None:
        """Remove an uncompleted claim after a failed execution."""
        with self.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM ois_idempotency_results "
                "WHERE invocation_id = %s AND status = 'PENDING'",
                (invocation_id,),
            )

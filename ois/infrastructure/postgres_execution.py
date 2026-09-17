"""DB-API PostgreSQL adapters for durable state and evidence.

The adapter accepts an existing DB-API connection factory, keeping psycopg optional
for callers and making transaction ownership explicit at the boundary.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Protocol

from ois.application.state import ExecutionState


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
                "SELECT state FROM execution_state WHERE execution_id = %s", (execution_id,)
            )
            row = cursor.fetchone()
            return ExecutionState(row[0]) if row else None

    def set_state(self, execution_id: str, state: ExecutionState) -> None:
        with self.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO execution_state (execution_id, state) VALUES (%s, %s) "
                "ON CONFLICT (execution_id) "
"DO UPDATE SET state = EXCLUDED.state, updated_at = now()",
                (execution_id, state.value),
            )

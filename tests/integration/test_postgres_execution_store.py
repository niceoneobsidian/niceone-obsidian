from __future__ import annotations

import psycopg
import pytest

from ois.application.state import ExecutionState
from ois.infrastructure.postgres_execution import PostgresExecutionStore


class Cursor:
    def __init__(self):
        self.queries = []
        self.row = ("pending",)

    def execute(self, query, params):
        self.queries.append((query, params))

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self):
        self.cursor_obj = Cursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def test_state_and_evidence_use_explicit_transactions():
    connections = []

    def factory():
        connection = Connection()
        connections.append(connection)
        return connection

    store = PostgresExecutionStore(factory)
    store.set_state("job-1", ExecutionState.AUTHORIZED)
    store.append_evidence("job-1", "authorization", {"decision": "allow"})
    assert len(connections) == 2
    assert all(connection.commits == 1 for connection in connections)


def test_postgres_execution_store_rejects_invalid_state_transition(
    migrated_postgres: str,
) -> None:
    from ois.application.state import ExecutionState

    def connection_factory():
        return psycopg.connect(migrated_postgres)

    store = PostgresExecutionStore(connection_factory)
    store.set_state("exec-guard-1", ExecutionState.PENDING)
    assert store.get_state("exec-guard-1") == ExecutionState.PENDING

    # PENDING -> VERIFIED is strictly forbidden by the state machine
    with pytest.raises(ValueError):
        store.set_state("exec-guard-1", ExecutionState.VERIFIED)

    # Persisted state remains unchanged
    assert store.get_state("exec-guard-1") == ExecutionState.PENDING


def test_postgres_evidence_is_append_only_and_rejects_mutations(
    migrated_postgres: str,
) -> None:
    def connection_factory():
        return psycopg.connect(migrated_postgres)

    store = PostgresExecutionStore(connection_factory)
    store.append_evidence("exec-immutable-1", "audit", {"event": "started"})

    conn = psycopg.connect(migrated_postgres)
    cursor = conn.cursor()

    try:
        # Attempting to UPDATE evidence must fail closed.
        with pytest.raises(
            psycopg.errors.RaiseException,
            match="append-only",
        ):
            cursor.execute(
                "UPDATE execution_evidence SET category = 'tampered' WHERE execution_id = %s",
                ("exec-immutable-1",),
            )

        conn.rollback()

        # Attempting to DELETE evidence must fail closed.
        with pytest.raises(
            psycopg.errors.RaiseException,
            match="append-only",
        ):
            cursor.execute(
                "DELETE FROM execution_evidence WHERE execution_id = %s",
                ("exec-immutable-1",),
            )

        conn.rollback()
    finally:
        cursor.close()
        conn.close()

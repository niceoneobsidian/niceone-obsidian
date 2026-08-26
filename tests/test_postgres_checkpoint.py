from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ois.kernel.postgres_checkpoint import PostgreSQLCheckpointStore
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import ExecutionStatus


class FakeCursor:
    def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.executed.append((sql, params))

    def fetchone(self) -> tuple[object, ...] | None:
        return self.rows.pop(0) if self.rows else None


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.fake_cursor = cursor
        self.commits = 0

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def commit(self) -> None:
        self.commits += 1


def context() -> ExecutionContext:
    return ExecutionContext(
        identity=ExecutionIdentity(
            execution_id=uuid4(),
            tenant_id="tenant-a",
            workflow_id="workflow-a",
            workflow_version="1",
        ),
        objective="resume me",
        status=ExecutionStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        current_node="node-2",
        working_memory={"completed": ["node-1"]},
    )


def test_save_uses_atomic_postgres_upsert() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    store = PostgreSQLCheckpointStore(lambda: connection)

    execution = context()
    store.save(execution)

    assert len(cursor.executed) == 1
    sql, params = cursor.executed[0]
    assert "ON CONFLICT (execution_id) DO UPDATE" in sql
    assert params[0] == execution.identity.execution_id
    assert params[1] == "tenant-a"
    assert params[4] == ExecutionStatus.RUNNING.value
    assert connection.commits == 1


def test_load_reconstructs_execution_context() -> None:
    execution = context()
    cursor = FakeCursor([(execution.to_dict(),)])
    connection = FakeConnection(cursor)
    store = PostgreSQLCheckpointStore(lambda: connection)

    restored = store.load(execution.identity.execution_id)

    assert restored.identity.execution_id == execution.identity.execution_id
    assert restored.identity.tenant_id == "tenant-a"
    assert restored.current_node == "node-2"
    assert restored.working_memory == {"completed": ["node-1"]}


def test_delete_commits() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    store = PostgreSQLCheckpointStore(lambda: connection)
    execution_id = uuid4()

    store.delete(execution_id)

    assert "DELETE FROM ois_execution_checkpoints" in cursor.executed[0][0]
    assert cursor.executed[0][1] == (execution_id,)
    assert connection.commits == 1


def test_exists_returns_true_when_row_exists() -> None:
    cursor = FakeCursor([(1,)])
    connection = FakeConnection(cursor)
    store = PostgreSQLCheckpointStore(lambda: connection)

    assert store.exists(uuid4()) is True

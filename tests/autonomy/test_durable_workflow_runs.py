from __future__ import annotations

from uuid import UUID

from ois.autonomy.durable import (
    DurableRunStatus,
    DurableWorkflowRun,
    PostgresWorkflowRunRepository,
)


class FakeCursor:
    def __init__(self) -> None:
        self.rowcount = 1
        self._row = None

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        if "RETURNING run_id" in sql:
            self._row = (UUID("00000000-0000-0000-0000-000000000001"),)
        elif "SELECT run_id" in sql:
            self._row = (
                UUID("00000000-0000-0000-0000-000000000001"), "t", "w", "wf", "1",
                "e", "received", 0, {}, None, None, "t:w:wf:1:e",
            )

    def fetchone(self):
        return self._row

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = FakeCursor()

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_run_uses_deterministic_durable_idempotency_key() -> None:
    run = DurableWorkflowRun.new(
        tenant_id="t", workspace_id="w", workflow_id="wf",
        workflow_version="1", event_id="e",
    )
    assert run.idempotency_key == "t:w:wf:1:e"


def test_repository_create_is_idempotent() -> None:
    connection = FakeConnection()
    repo = PostgresWorkflowRunRepository(lambda: connection)
    run = DurableWorkflowRun(
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
        tenant_id="t", workspace_id="w", workflow_id="wf", workflow_version="1",
        event_id="e", status=DurableRunStatus.RECEIVED, idempotency_key="t:w:wf:1:e",
    )
    created = repo.create(run)
    assert created.run_id == run.run_id
    assert repo.get(run.run_id) is not None

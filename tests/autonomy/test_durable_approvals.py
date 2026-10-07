from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ois.autonomy.durable_approvals import PostgresApprovalStore


class Cursor:
    def __init__(self):
        self.row = None

    def execute(self, sql, params=()):
        if "SELECT approval_id" in sql:
            now = datetime.now(UTC)
            self.row = (
                "approval-1",
                "t",
                "w",
                "wf",
                "event-1",
                "approve",
                "approved",
                now,
                now + timedelta(hours=1),
                "actor",
                now,
                {"source": "github"},
                "github",
                "source.event",
            )

    def fetchone(self):
        return self.row

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class Connection:
    def __init__(self):
        self.c = Cursor()

    def cursor(self):
        return self.c

    def commit(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_durable_approval_reconstructs_original_event_after_restart() -> None:
    store = PostgresApprovalStore(lambda: Connection())
    event = store.resume_event("approval-1")
    assert event.event_type == "source.event"
    assert event.source_id == "github"
    assert event.payload["source"] == "github"

from __future__ import annotations

from uuid import UUID

from ois.autonomy.side_effects import PostgresSideEffectLedger


class Cursor:
    def __init__(self):
        self.rowcount = 1
        self.row = (
            UUID("00000000-0000-0000-0000-000000000004"),
            "t",
            "w",
            UUID("00000000-0000-0000-0000-000000000005"),
            "inv",
            "key",
            "cap",
            {"x": 1},
            "prepared",
            None,
            None,
            None,
        )

    def execute(self, sql, params=()):
        return None

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


def test_prepare_is_safe_to_retry_by_idempotency_key() -> None:
    connection = Connection()
    ledger = PostgresSideEffectLedger(lambda: connection)
    first = ledger.prepare(
        tenant_id="t",
        workspace_id="w",
        run_id=UUID("00000000-0000-0000-0000-000000000005"),
        invocation_id="inv",
        idempotency_key="key",
        capability_id="cap",
        request={"x": 1},
    )
    second = ledger.prepare(
        tenant_id="t",
        workspace_id="w",
        run_id=UUID("00000000-0000-0000-0000-000000000005"),
        invocation_id="inv",
        idempotency_key="key",
        capability_id="cap",
        request={"x": 1},
    )
    assert first.effect_id == second.effect_id

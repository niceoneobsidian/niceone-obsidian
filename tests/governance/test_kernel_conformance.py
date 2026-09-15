from __future__ import annotations

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from ois.kernel.evidence import EvidenceEvent, EvidenceLedger, SQLiteEvidenceLedger


def test_evidence_event_is_immutable_and_serializable() -> None:
    execution_id = uuid4()
    event = EvidenceEvent(execution_id=execution_id, event_type="authorized")

    assert event.to_dict()["execution_id"] == str(execution_id)
    assert event.to_dict()["event_type"] == "authorized"
    with pytest.raises(FrozenInstanceError):
        event.event_type = "tampered"  # type: ignore[misc]


def test_in_memory_ledger_is_append_only_and_filters_by_execution() -> None:
    ledger = EvidenceLedger()
    first_id = uuid4()
    second_id = uuid4()

    first = ledger.record(first_id, "authorized", {"capability": "execute"})
    ledger.record(second_id, "authorized")

    assert ledger.list(first_id) == (first,)
    assert ledger.count(first_id) == 1
    assert ledger.count(second_id) == 1

    with pytest.raises(AttributeError):
        ledger.list(first_id).append(first)  # type: ignore[attr-defined]


def test_sqlite_ledger_preserves_event_order_and_deduplicates_event_ids(tmp_path) -> None:
    ledger = SQLiteEvidenceLedger(str(tmp_path / "evidence.db"))
    execution_id = uuid4()
    first = ledger.record(execution_id, "authorized", {"step": 1})
    second = ledger.record(execution_id, "executing", {"step": 2})

    ledger.append(first)
    ledger.append(second)
    ledger.append(first)

    events = ledger.list(execution_id)
    assert [event.event_type for event in events] == ["authorized", "executing"]
    assert ledger.count(execution_id) == 2
    ledger.close()


def test_kernel_rejects_invalid_evidence_payloads() -> None:
    ledger = EvidenceLedger()
    execution_id = uuid4()

    with pytest.raises(TypeError):
        ledger.record(execution_id, "invalid", {"ok": object()})

from datetime import UTC, datetime

from ois.domains.social_growth.evidence import SQLiteEvidenceLedger
from ois.domains.social_growth.persistence import SQLiteSocialEventStore
from ois.domains.social_growth.schemas import Evidence, SocialEvent


def make_event(event_id: str = "evt-1") -> SocialEvent:
    return SocialEvent(
        event_id=event_id,
        platform="tiktok",
        event_type="post",
        occurred_at=datetime(2026, 8, 23, tzinfo=UTC),
        external_id="post-1",
        text="A useful social signal",
        metrics={"views": 1000, "likes": 100},
        evidence=[Evidence(source_id="tiktok", uri="https://example.test/post-1")],
    )


def test_event_store_is_append_only_and_idempotent() -> None:
    store = SQLiteSocialEventStore()
    event = make_event()

    assert store.append(event) is True
    assert store.append(event) is False
    assert store.get(event.event_id) == event
    assert store.list(platform="tiktok") == [event]
    store.close()


def test_external_id_deduplicates_same_platform() -> None:
    store = SQLiteSocialEventStore()
    first = make_event("evt-1")
    second = make_event("evt-2")

    assert store.append(first) is True
    assert store.append(second) is False
    assert store.get("evt-2") is None
    store.close()


def test_evidence_ledger_preserves_provenance() -> None:
    ledger = SQLiteEvidenceLedger()
    evidence = Evidence(
        source_id="source-1",
        uri="https://example.test/item",
        excerpt="observed signal",
        confidence=0.9,
    )

    evidence_id = ledger.record(evidence)
    assert evidence_id > 0
    assert ledger.list(source_id="source-1") == [evidence]
    ledger.close()

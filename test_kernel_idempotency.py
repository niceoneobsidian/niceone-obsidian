from ois.kernel import InvocationResult, InvocationStatus
from ois.kernel.idempotency import InMemoryIdempotencyStore


def make_result(invocation_id="inv-1"):
    return InvocationResult(
        invocation_id=invocation_id,
        capability_id="test.capability",
        status=InvocationStatus.SUCCEEDED,
        output={"value": 42},
    )


def test_idempotency_store_returns_cached_result():
    store = InMemoryIdempotencyStore()
    result = make_result()

    store.put("inv-1", result)

    assert store.get("inv-1") is result
    assert store.exists("inv-1") is True


def test_idempotency_store_returns_none_for_unknown_invocation():
    store = InMemoryIdempotencyStore()

    assert store.get("missing") is None
    assert store.exists("missing") is False


def test_same_invocation_id_reuses_cached_result():
    store = InMemoryIdempotencyStore()

    first = make_result()
    second = make_result()

    store.put("inv-1", first)
    store.put("inv-1", second)

    assert store.get("inv-1") is second


def test_different_invocation_ids_are_distinct():
    store = InMemoryIdempotencyStore()

    first = make_result("inv-1")
    second = make_result("inv-2")

    store.put("inv-1", first)
    store.put("inv-2", second)

    assert store.get("inv-1") is first
    assert store.get("inv-2") is second
    assert store.get("inv-1") != store.get("inv-2")


def test_idempotency_is_public_kernel_api():
    from ois.kernel import (
        IdempotencyStore,
        InMemoryIdempotencyStore,
    )

    assert IdempotencyStore is not None
    assert InMemoryIdempotencyStore is not None


def test_sqlite_idempotency_survives_store_recreation(tmp_path):
    from ois.kernel.idempotency import SQLiteIdempotencyStore

    database = tmp_path / "idempotency.db"

    first_store = SQLiteIdempotencyStore(str(database))

    first = make_result("persistent-001")

    first_store.put(
        "persistent-001",
        first,
    )

    first_store.close()

    # Simulate a runtime/process restart by creating an entirely
    # new store object against the same durable database.
    second_store = SQLiteIdempotencyStore(str(database))

    restored = second_store.get("persistent-001")

    assert restored is not None
    assert restored.invocation_id == "persistent-001"
    assert restored.capability_id == first.capability_id
    assert restored.status == first.status
    assert restored.output == first.output

    second_store.close()


def test_sqlite_idempotency_unknown_invocation_returns_none(tmp_path):
    from ois.kernel.idempotency import SQLiteIdempotencyStore

    database = tmp_path / "idempotency.db"

    store = SQLiteIdempotencyStore(str(database))

    assert store.get("missing") is None
    assert store.exists("missing") is False

    store.close()


def test_sqlite_idempotency_is_public_kernel_api():
    from ois.kernel import SQLiteIdempotencyStore

    assert SQLiteIdempotencyStore is not None

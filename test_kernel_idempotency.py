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

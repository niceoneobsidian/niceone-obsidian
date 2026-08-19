from __future__ import annotations

from threading import RLock
from typing import Protocol

from .contracts import InvocationResult


class IdempotencyStore(Protocol):
    def get(self, invocation_id: str) -> InvocationResult | None:
        ...

    def put(self, invocation_id: str, result: InvocationResult) -> None:
        ...


class InMemoryIdempotencyStore:
    """
    Reference idempotency implementation.

    Caches an InvocationResult by caller-supplied invocation_id so that
    re-submitting the same logical invocation does not re-execute a
    capability's side effects.

    Identity is scoped to the invocation_id the caller provides -- two
    calls with the same input but different invocation_ids are always
    treated as distinct invocations. This is a deliberate design choice:
    identity is explicit (caller-supplied), not inferred from payload
    contents.
    """

    def __init__(self) -> None:
        self._store: dict[str, InvocationResult] = {}
        self._lock = RLock()

    def get(self, invocation_id: str) -> InvocationResult | None:
        with self._lock:
            return self._store.get(invocation_id)

    def put(self, invocation_id: str, result: InvocationResult) -> None:
        with self._lock:
            self._store[invocation_id] = result

    def exists(self, invocation_id: str) -> bool:
        with self._lock:
            return invocation_id in self._store

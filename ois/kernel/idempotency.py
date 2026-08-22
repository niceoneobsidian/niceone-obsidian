from __future__ import annotations

from threading import RLock
from typing import Protocol

from .contracts import InvocationResult


class IdempotencyStore(Protocol):
    def get(self, invocation_id: str) -> InvocationResult | None: ...

    def put(self, invocation_id: str, result: InvocationResult) -> None: ...


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


class SQLiteIdempotencyStore:
    """
    Durable idempotency implementation backed by SQLite.

    The store persists completed InvocationResult objects so that
    idempotency survives creation of a new runtime/store instance
    and therefore provides a local restart/recovery boundary.

    SQLite is used here as a deterministic reference durable backend.
    Production deployments can replace this implementation with
    PostgreSQL or another durable state service without changing the
    IdempotencyStore contract.
    """

    def __init__(self, path: str) -> None:
        import json
        import sqlite3

        self._json = json
        self._sqlite3 = sqlite3
        self._connection = sqlite3.connect(
            path,
            check_same_thread=False,
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS idempotency_results (
                invocation_id TEXT PRIMARY KEY,
                result_json TEXT NOT NULL
            )
            """
        )
        self._connection.commit()
        self._lock = RLock()

    def get(self, invocation_id: str) -> InvocationResult | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT result_json
                FROM idempotency_results
                WHERE invocation_id = ?
                """,
                (invocation_id,),
            ).fetchone()

        if row is None:
            return None

        data = self._json.loads(row[0])

        from .types import InvocationStatus

        return InvocationResult(
            invocation_id=data["invocation_id"],
            capability_id=data["capability_id"],
            status=InvocationStatus(data["status"]),
            output=data.get("output"),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )

    def put(
        self,
        invocation_id: str,
        result: InvocationResult,
    ) -> None:
        payload = self._json.dumps(
            {
                "invocation_id": result.invocation_id,
                "capability_id": result.capability_id,
                "status": result.status.value,
                "output": result.output,
                "error": result.error,
                "started_at": result.started_at,
                "completed_at": result.completed_at,
                "metadata": dict(result.metadata),
            },
            sort_keys=True,
        )

        with self._lock:
            self._connection.execute(
                """
                INSERT INTO idempotency_results (
                    invocation_id,
                    result_json
                )
                VALUES (?, ?)
                ON CONFLICT(invocation_id)
                DO UPDATE SET result_json = excluded.result_json
                """,
                (
                    invocation_id,
                    payload,
                ),
            )
            self._connection.commit()

    def exists(self, invocation_id: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT 1
                FROM idempotency_results
                WHERE invocation_id = ?
                """,
                (invocation_id,),
            ).fetchone()

        return row is not None

    def close(self) -> None:
        with self._lock:
            self._connection.close()

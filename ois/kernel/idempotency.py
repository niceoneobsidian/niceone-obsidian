from __future__ import annotations

import json
import sqlite3
from threading import RLock
from typing import Protocol

from .contracts import InvocationResult
from .types import InvocationStatus


class IdempotencyStore(Protocol):
    def get(self, invocation_id: str) -> InvocationResult | None: ...

    def put(self, invocation_id: str, result: InvocationResult) -> None: ...


class InMemoryIdempotencyStore:
    """Process-local completed-invocation cache."""

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
    """Durable completed-invocation store using SQLite transactions.

    Only terminal results are persisted. A failed or interrupted attempt is
    therefore eligible for recovery rather than being permanently treated as
    completed work. ``INSERT OR IGNORE`` also makes the first terminal result
    authoritative and prevents a later replay from replacing it.
    """

    def __init__(self, path: str) -> None:
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
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
                "SELECT result_json FROM idempotency_results WHERE invocation_id = ?",
                (invocation_id,),
            ).fetchone()
        if row is None:
            return None
        data = json.loads(row[0])
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

    def put(self, invocation_id: str, result: InvocationResult) -> None:
        if result.status not in {InvocationStatus.SUCCEEDED, InvocationStatus.CANCELLED}:
            return
        payload = json.dumps(
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
                INSERT OR IGNORE INTO idempotency_results(invocation_id, result_json)
                VALUES (?, ?)
                """,
                (invocation_id, payload),
            )
            self._connection.commit()

    def exists(self, invocation_id: str) -> bool:
        return self.get(invocation_id) is not None

    def close(self) -> None:
        with self._lock:
            self._connection.close()

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from threading import RLock
from time import monotonic, sleep
from typing import Any, Protocol

from .contracts import InvocationResult


class IdempotencyStore(Protocol):
    def get(self, invocation_id: str) -> InvocationResult | None: ...
    def put(self, invocation_id: str, result: InvocationResult) -> None: ...
    def claim(self, invocation_id: str, lease_seconds: float = 30.0) -> "IdempotencyClaim": ...


@dataclass(frozen=True)
class IdempotencyClaim:
    acquired: bool
    result: InvocationResult | None = None
    pending: bool = False


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._store: dict[str, InvocationResult] = {}
        self._pending: dict[str, float] = {}
        self._lock = RLock()

    def get(self, invocation_id: str) -> InvocationResult | None:
        with self._lock:
            return self._store.get(invocation_id)

    def put(self, invocation_id: str, result: InvocationResult) -> None:
        with self._lock:
            self._store[invocation_id] = result
            self._pending.pop(invocation_id, None)

    def claim(self, invocation_id: str, lease_seconds: float = 30.0) -> IdempotencyClaim:
        with self._lock:
            result = self._store.get(invocation_id)
            if result is not None:
                return IdempotencyClaim(False, result=result)
            now = monotonic()
            expires = self._pending.get(invocation_id)
            if expires is None or expires <= now:
                self._pending[invocation_id] = now + lease_seconds
                return IdempotencyClaim(True)
            return IdempotencyClaim(False, pending=True)

    def wait(self, invocation_id: str, timeout_seconds: float = 30.0) -> InvocationResult | None:
        deadline = monotonic() + timeout_seconds
        while monotonic() < deadline:
            result = self.get(invocation_id)
            if result is not None:
                return result
            sleep(0.01)
        return None

    def exists(self, invocation_id: str) -> bool:
        return self.get(invocation_id) is not None


class SQLiteIdempotencyStore:
    """Durable local store with transactional claim/lease semantics."""

    def __init__(self, path: str) -> None:
        import sqlite3

        self._connection = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS idempotency_results (
                invocation_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                result_json TEXT,
                lease_until REAL
            )
            """
        )
        self._connection.commit()
        self._lock = RLock()

    @staticmethod
    def _encode(result: InvocationResult) -> str:
        return json.dumps(
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

    @staticmethod
    def _decode(payload: str) -> InvocationResult:
        from .types import InvocationStatus

        data = json.loads(payload)
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

    def get(self, invocation_id: str) -> InvocationResult | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT status, result_json FROM idempotency_results WHERE invocation_id = ?",
                (invocation_id,),
            ).fetchone()
        if row is None or row[0] != "COMPLETED" or row[1] is None:
            return None
        return self._decode(row[1])

    def put(self, invocation_id: str, result: InvocationResult) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO idempotency_results(invocation_id, status, result_json, lease_until)
                VALUES (?, 'COMPLETED', ?, NULL)
                ON CONFLICT(invocation_id) DO UPDATE SET
                    status='COMPLETED', result_json=excluded.result_json, lease_until=NULL
                """,
                (invocation_id, self._encode(result)),
            )
            self._connection.commit()

    def claim(self, invocation_id: str, lease_seconds: float = 30.0) -> IdempotencyClaim:
        now = monotonic()
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT status, result_json, lease_until FROM idempotency_results WHERE invocation_id = ?",
                (invocation_id,),
            ).fetchone()
            if row is None:
                self._connection.execute(
                    "INSERT INTO idempotency_results(invocation_id, status, lease_until) VALUES (?, 'PENDING', ?)",
                    (invocation_id, now + lease_seconds),
                )
                self._connection.commit()
                return IdempotencyClaim(True)
            if row[0] == "COMPLETED" and row[1] is not None:
                self._connection.commit()
                return IdempotencyClaim(False, result=self._decode(row[1]))
            if row[2] is None or float(row[2]) <= now:
                self._connection.execute(
                    "UPDATE idempotency_results SET status='PENDING', lease_until=? WHERE invocation_id=?",
                    (now + lease_seconds, invocation_id),
                )
                self._connection.commit()
                return IdempotencyClaim(True)
            self._connection.commit()
            return IdempotencyClaim(False, pending=True)

    def wait(self, invocation_id: str, timeout_seconds: float = 30.0) -> InvocationResult | None:
        deadline = monotonic() + timeout_seconds
        while monotonic() < deadline:
            result = self.get(invocation_id)
            if result is not None:
                return result
            sleep(0.02)
        return None

    def exists(self, invocation_id: str) -> bool:
        return self.get(invocation_id) is not None

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class PostgresIdempotencyStore:
    """PostgreSQL idempotency store with atomic claim/lease semantics."""

    def __init__(self, dsn: str, *, connect_timeout: int = 10) -> None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL backend requires the psycopg package") from exc
        self._psycopg = psycopg
        self._dsn = dsn
        self._connect_timeout = connect_timeout

    def _connection(self) -> Any:
        return self._psycopg.connect(self._dsn, connect_timeout=self._connect_timeout)

    @staticmethod
    def _decode(payload: dict[str, Any]) -> InvocationResult:
        from .types import InvocationStatus

        return InvocationResult(
            invocation_id=payload["invocation_id"],
            capability_id=payload["capability_id"],
            status=InvocationStatus(payload["status"]),
            output=payload.get("output"),
            error=payload.get("error"),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            metadata=payload.get("metadata", {}),
        )

    def get(self, invocation_id: str) -> InvocationResult | None:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT result_json FROM ois_idempotency WHERE invocation_id=%s AND status='COMPLETED'",
                    (invocation_id,),
                )
                row = cursor.fetchone()
        return None if row is None else self._decode(row[0])

    def claim(self, invocation_id: str, lease_seconds: float = 30.0) -> IdempotencyClaim:
        lease = timedelta(seconds=lease_seconds)
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (invocation_id,))
                cursor.execute(
                    "SELECT status, result_json, lease_until FROM ois_idempotency WHERE invocation_id=%s FOR UPDATE",
                    (invocation_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    cursor.execute(
                        "INSERT INTO ois_idempotency(invocation_id,status,lease_until) VALUES(%s,'PENDING',clock_timestamp()+%s)",
                        (invocation_id, lease),
                    )
                    return IdempotencyClaim(True)
                if row[0] == "COMPLETED" and row[1] is not None:
                    return IdempotencyClaim(False, result=self._decode(row[1]))
                if row[2] is None or row[2] <= datetime.now(UTC):
                    cursor.execute(
                        "UPDATE ois_idempotency SET status='PENDING', lease_until=clock_timestamp()+%s WHERE invocation_id=%s",
                        (lease, invocation_id),
                    )
                    return IdempotencyClaim(True)
                return IdempotencyClaim(False, pending=True)

    def put(self, invocation_id: str, result: InvocationResult) -> None:
        payload = {
            "invocation_id": result.invocation_id,
            "capability_id": result.capability_id,
            "status": result.status.value,
            "output": result.output,
            "error": result.error,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "metadata": dict(result.metadata),
        }
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ois_idempotency
                    SET status='COMPLETED', result_json=%s, lease_until=NULL, completed_at=clock_timestamp()
                    WHERE invocation_id=%s
                    """,
                    (json.dumps(payload), invocation_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(f"Unknown idempotency invocation {invocation_id}")

    def wait(self, invocation_id: str, timeout_seconds: float = 30.0) -> InvocationResult | None:
        deadline = monotonic() + timeout_seconds
        while monotonic() < deadline:
            result = self.get(invocation_id)
            if result is not None:
                return result
            sleep(0.05)
        return None

    def exists(self, invocation_id: str) -> bool:
        return self.get(invocation_id) is not None

    def close(self) -> None:
        return None

# =====================================================================
# NICEONE OBSIDIAN INTELLIGENCE SYSTEM (OIS)
# Durable Execution Primitives — v3.0.0
# =====================================================================
# Persistent execution store and worker queue behind the OIS runtime
# fabric contracts.
#
# Backend: SQLite (stdlib) — dependency-light for the first durable
# implementation. Production path: swap to PostgreSQL via the same
# interface contract.
#
# Scope boundary:
#   This module is an execution store and queue ONLY.
#   Kernel policy, authorization, validation, and recovery remain
#   authoritative above this layer and are never duplicated here.
# =====================================================================

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any, cast

# =====================================================================
# LOGGING
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("OIS.Persistence")


# =====================================================================
# UTILITIES
# =====================================================================
def _now() -> str:
    """Returns the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _dumps(value: Any) -> str | None:
    """Serializes a value to JSON, returning None if value is None."""
    return json.dumps(value) if value is not None else None


def _loads(value: str | None) -> Any:
    """Deserializes a JSON string, returning None if value is None."""
    return json.loads(value) if value is not None else None


# =====================================================================
# EXCEPTIONS — typed failure surface
# =====================================================================
class OISPersistenceError(Exception):
    """Base exception for all OIS persistence layer errors."""


class ExecutionNotFoundError(OISPersistenceError):
    """Raised when an execution_id does not exist in the store."""


class JobNotFoundError(OISPersistenceError):
    """Raised when a job_id does not exist in the queue."""


class JobOwnershipError(OISPersistenceError):
    """Raised when a worker attempts to act on a job it does not own."""


class DuplicateExecutionError(OISPersistenceError):
    """Raised when an execution_id already exists (append-only guarantee)."""


class DuplicateJobError(OISPersistenceError):
    """Raised when a job_id already exists in the queue."""


class InvalidStatusTransitionError(OISPersistenceError):
    """Raised when a status transition violates the state machine."""


# =====================================================================
# STATUS STATE MACHINES
# =====================================================================
# Execution:  ready → running → succeeded | failed
# Job:        pending → leased → completed | failed
#                              ↘ pending (retry)

_VALID_EXECUTION_TRANSITIONS: dict[str, set[str]] = {
    "ready": {"running"},
    "running": {"succeeded", "failed"},
    "succeeded": set(),
    "failed": set(),
}

_VALID_JOB_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"leased"},
    "leased": {"completed", "failed", "pending"},  # pending = retry
    "completed": set(),
    "failed": set(),
}


def _validate_execution_transition(current: str, target: str) -> None:
    allowed = _VALID_EXECUTION_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStatusTransitionError(
            f"Execution status transition '{current}' → '{target}' is not permitted. "
            f"Allowed: {allowed or 'none (terminal state)'}."
        )


def _validate_job_transition(current: str, target: str) -> None:
    allowed = _VALID_JOB_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStatusTransitionError(
            f"Job status transition '{current}' → '{target}' is not permitted. "
            f"Allowed: {allowed or 'none (terminal state)'}."
        )


# =====================================================================
# DATA CONTRACTS — typed, frozen, immutable records
# =====================================================================
@dataclass(frozen=True)
class ExecutionRecord:
    """
    Immutable snapshot of a workflow execution state.

    Statuses:
        ready       — created, not yet picked up
        running     — actively executing, checkpoint may be present
        succeeded   — terminal success with result
        failed      — terminal failure with error
    """

    execution_id: str
    workflow_id: str
    status: str
    payload: dict[str, Any]
    result: Any = None
    error: dict[str, str] | None = None
    checkpoint: dict[str, Any] | None = None
    updated_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class QueueJob:
    """
    Immutable snapshot of a worker queue job.

    Statuses:
        pending     — waiting to be claimed
        leased      — claimed by a worker, being processed
        completed   — terminal success
        failed      — terminal failure after max retries
    """

    job_id: str
    queue: str
    payload: dict[str, Any]
    attempts: int = 0
    lease_owner: str | None = None
    status: str = "pending"
    updated_at: str = field(default_factory=_now)


# =====================================================================
# BASE STORE — shared SQLite connection management
# =====================================================================
class _SQLiteBase:
    """
    Shared connection management and locking for SQLite-backed stores.

    Thread safety: RLock guards all write paths.
    Reads use the same connection under row_factory = sqlite3.Row.
    """

    def __init__(self, database: str = ":memory:") -> None:
        self._db = database
        self._conn = sqlite3.connect(database, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._lock = RLock()

    @contextmanager
    def _write(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that acquires the write lock and wraps in a transaction."""
        with self._lock, self._conn:
            yield self._conn

    def _read(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Thread-safe read returning all matching rows."""
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _read_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        """Thread-safe read returning the first matching row or None."""
        with self._lock:
            return self._conn.execute(sql, params).fetchone()  # type: ignore

    def close(self) -> None:
        """Closes the underlying SQLite connection."""
        self._conn.close()


# =====================================================================
# SQLITE EXECUTION STORE
# =====================================================================
class SQLiteExecutionStore(_SQLiteBase):
    """
    Persistent execution and checkpoint store for resumable OIS workflows.

    Responsibilities:
        - Create and track workflow execution lifecycle
        - Store durable checkpoints for mid-execution resumption
        - Record terminal results and structured error payloads
        - Enforce append-only creation (no duplicate execution_ids)
        - Enforce valid status state machine transitions

    Not responsible for:
        - Policy or authorization (kernel layer)
        - Retry orchestration (recovery engine)
        - Agent or capability registration (registry layer)
    """

    _LOG = logging.getLogger("OIS.ExecutionStore")

    def __init__(self, database: str = ":memory:") -> None:
        super().__init__(database)
        self._initialize()

    def _initialize(self) -> None:
        with self._write() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id  TEXT PRIMARY KEY,
                    workflow_id   TEXT NOT NULL,
                    status        TEXT NOT NULL DEFAULT 'ready',
                    payload       TEXT NOT NULL,
                    result        TEXT,
                    error         TEXT,
                    checkpoint    TEXT,
                    updated_at    TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_executions_workflow
                ON executions (workflow_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_executions_status
                ON executions (status)
                """
            )

    # ── Public API ────────────────────────────────────────────────────

    def create(
        self,
        execution_id: str,
        workflow_id: str,
        payload: dict[str, Any],
    ) -> ExecutionRecord:
        """
        Creates a new execution record in 'ready' status.
        Raises DuplicateExecutionError if execution_id already exists.
        """
        existing = self._read_one(
            "SELECT execution_id FROM executions WHERE execution_id = ?",
            (execution_id,),
        )
        if existing:
            raise DuplicateExecutionError(
                f"Execution '{execution_id}' already exists. Execution store is append-only."
            )

        now = _now()
        with self._write() as conn:
            conn.execute(
                """
                INSERT INTO executions
                (execution_id, workflow_id, status, payload, updated_at)
                VALUES (?, ?, 'ready', ?, ?)
                """,
                (execution_id, workflow_id, json.dumps(payload), now),
            )

        self._LOG.info(
            "CREATE | execution_id=%s workflow_id=%s",
            execution_id,
            workflow_id,
        )
        return self.get(execution_id)

    def checkpoint(
        self,
        execution_id: str,
        checkpoint: dict[str, Any],
    ) -> ExecutionRecord:
        """
        Persists an intermediate checkpoint and advances status to 'running'.
        Allows resumption after failure or restart.
        """
        record = self.get(execution_id)
        _validate_execution_transition(record.status, "running")

        with self._write() as conn:
            conn.execute(
                """
                UPDATE executions
                SET checkpoint = ?,
                    status     = 'running',
                    updated_at = ?
                WHERE execution_id = ?
                """,
                (json.dumps(checkpoint), _now(), execution_id),
            )

        self._LOG.info("CHECKPOINT | execution_id=%s", execution_id)
        return self.get(execution_id)

    def complete(
        self,
        execution_id: str,
        result: Any,
    ) -> ExecutionRecord:
        """
        Marks an execution as 'succeeded' with its final result payload.
        Terminal state — no further transitions are permitted.
        """
        return self._set_terminal(execution_id, target_status="succeeded", result=result)

    def fail(
        self,
        execution_id: str,
        error: dict[str, str],
    ) -> ExecutionRecord:
        """
        Marks an execution as 'failed' with a structured error payload.
        Terminal state — no further transitions are permitted.
        """
        return self._set_terminal(execution_id, target_status="failed", error=error)

    def get(self, execution_id: str) -> ExecutionRecord:
        """
        Retrieves an execution record by ID.
        Raises ExecutionNotFoundError if not found.
        """
        row = self._read_one(
            "SELECT * FROM executions WHERE execution_id = ?",
            (execution_id,),
        )
        if row is None:
            raise ExecutionNotFoundError(f"Execution '{execution_id}' not found in store.")
        return self._record(row)

    def list_by_status(self, status: str) -> list[ExecutionRecord]:
        """Returns all executions matching the given status."""
        rows = self._read(
            "SELECT * FROM executions WHERE status = ? ORDER BY updated_at",
            (status,),
        )
        return [self._record(r) for r in rows]

    def list_by_workflow(self, workflow_id: str) -> list[ExecutionRecord]:
        """Returns all executions for a given workflow_id."""
        rows = self._read(
            "SELECT * FROM executions WHERE workflow_id = ? ORDER BY updated_at",
            (workflow_id,),
        )
        return [self._record(r) for r in rows]

    # ── Internal helpers ──────────────────────────────────────────────

    def _set_terminal(
        self,
        execution_id: str,
        target_status: str,
        *,
        result: Any = None,
        error: dict[str, str] | None = None,
    ) -> ExecutionRecord:
        record = self.get(execution_id)
        _validate_execution_transition(record.status, target_status)

        with self._write() as conn:
            conn.execute(
                """
                UPDATE executions
                SET status     = ?,
                    result     = ?,
                    error      = ?,
                    updated_at = ?
                WHERE execution_id = ?
                """,
                (
                    target_status,
                    _dumps(result),
                    _dumps(error),
                    _now(),
                    execution_id,
                ),
            )

        self._LOG.info(
            "TERMINAL | execution_id=%s status=%s",
            execution_id,
            target_status,
        )
        return self.get(execution_id)

    @staticmethod
    def _record(row: sqlite3.Row) -> ExecutionRecord:
        return ExecutionRecord(
            execution_id=row["execution_id"],
            workflow_id=row["workflow_id"],
            status=row["status"],
            payload=json.loads(row["payload"]),
            result=_loads(row["result"]),
            error=_loads(row["error"]),
            checkpoint=_loads(row["checkpoint"]),
            updated_at=row["updated_at"],
        )


# =====================================================================
# SQLITE WORKER QUEUE
# =====================================================================
class SQLiteWorkerQueue(_SQLiteBase):
    """
    Durable SQLite-backed worker queue with explicit leases and bounded retries.

    Design:
        - Lease-based ownership: only the claiming worker may retry or acknowledge
        - Explicit status state machine: pending → leased → completed | failed
        - Attempt counter incremented on every retry
        - Duplicate job_id raises DuplicateJobError (idempotent enqueue is caller's responsibility)
        - Ownership violation raises JobOwnershipError (not a generic exception)

    Not responsible for:
        - Max-retry enforcement (recovery engine or caller decides)
        - Dead-letter queue routing (caller promotes failed jobs)
        - Agent or capability authorization (kernel layer)
    """

    _LOG = logging.getLogger("OIS.WorkerQueue")

    def __init__(self, database: str = ":memory:") -> None:
        super().__init__(database)
        self._initialize()

    def _initialize(self) -> None:
        with self._write() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS worker_jobs (
                    job_id      TEXT PRIMARY KEY,
                    queue       TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    attempts    INTEGER NOT NULL DEFAULT 0,
                    lease_owner TEXT,
                    status      TEXT NOT NULL DEFAULT 'pending',
                    updated_at  TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_worker_jobs_queue_status
                ON worker_jobs (queue, status, updated_at)
                """
            )

    # ── Public API ────────────────────────────────────────────────────

    def enqueue(
        self,
        job_id: str,
        queue: str,
        payload: dict[str, Any],
    ) -> QueueJob:
        """
        Enqueues a new job in 'pending' status.
        Raises DuplicateJobError if job_id already exists.
        """
        existing = self._read_one(
            "SELECT job_id FROM worker_jobs WHERE job_id = ?",
            (job_id,),
        )
        if existing:
            raise DuplicateJobError(f"Job '{job_id}' already exists in queue '{queue}'.")

        now = _now()
        with self._write() as conn:
            conn.execute(
                """
                INSERT INTO worker_jobs
                (job_id, queue, payload, attempts, lease_owner, status, updated_at)
                VALUES (?, ?, ?, 0, NULL, 'pending', ?)
                """,
                (job_id, queue, json.dumps(payload), now),
            )

        self._LOG.info(
            "ENQUEUE | job_id=%s queue=%s",
            job_id,
            queue,
        )
        return self.get(job_id)

    def claim(
        self,
        queue: str,
        worker_id: str,
    ) -> QueueJob | None:
        """
        Atomically claims the oldest pending job in the given queue.
        Returns None if no pending jobs are available.
        Double-checks ownership on UPDATE to prevent race conditions.
        """
        with self._write() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM worker_jobs
                WHERE queue       = ?
                  AND status      = 'pending'
                  AND lease_owner IS NULL
                ORDER BY updated_at ASC, job_id ASC
                LIMIT 1
                """,
                (queue,),
            ).fetchone()

            if row is None:
                return None

            conn.execute(
                """
                UPDATE worker_jobs
                SET lease_owner = ?,
                    status      = 'leased',
                    updated_at  = ?
                WHERE job_id      = ?
                  AND status      = 'pending'
                  AND lease_owner IS NULL
                """,
                (worker_id, _now(), row["job_id"]),
            )

        self._LOG.info(
            "CLAIM | job_id=%s queue=%s worker_id=%s",
            row["job_id"],
            queue,
            worker_id,
        )
        return self.get(row["job_id"])

    def retry(
        self,
        job_id: str,
        worker_id: str,
    ) -> QueueJob:
        """
        Returns a leased job to 'pending' and increments its attempt counter.
        Only the owning worker may call this.
        Raises JobOwnershipError if the caller does not own the lease.
        """
        self._assert_ownership(job_id, worker_id, expected_status="leased")

        with self._write() as conn:
            conn.execute(
                """
                UPDATE worker_jobs
                SET attempts    = attempts + 1,
                    lease_owner = NULL,
                    status      = 'pending',
                    updated_at  = ?
                WHERE job_id      = ?
                  AND lease_owner = ?
                """,
                (_now(), job_id, worker_id),
            )

        self._LOG.info(
            "RETRY | job_id=%s worker_id=%s",
            job_id,
            worker_id,
        )
        return self.get(job_id)

    def acknowledge(
        self,
        job_id: str,
        worker_id: str,
    ) -> QueueJob:
        """
        Marks a leased job as 'completed' — terminal success.
        Only the owning worker may call this.
        Raises JobOwnershipError if the caller does not own the lease.
        """
        self._assert_ownership(job_id, worker_id, expected_status="leased")

        with self._write() as conn:
            conn.execute(
                """
                UPDATE worker_jobs
                SET status      = 'completed',
                    updated_at  = ?
                WHERE job_id      = ?
                  AND lease_owner = ?
                """,
                (_now(), job_id, worker_id),
            )

        self._LOG.info(
            "ACKNOWLEDGE | job_id=%s worker_id=%s",
            job_id,
            worker_id,
        )
        return self.get(job_id)

    def fail_job(
        self,
        job_id: str,
        worker_id: str,
    ) -> QueueJob:
        """
        Marks a leased job as 'failed' — terminal failure state.
        Only the owning worker may call this.
        Caller is responsible for promoting to dead-letter queue if required.
        Raises JobOwnershipError if the caller does not own the lease.
        """
        self._assert_ownership(job_id, worker_id, expected_status="leased")

        with self._write() as conn:
            conn.execute(
                """
                UPDATE worker_jobs
                SET status      = 'failed',
                    attempts    = attempts + 1,
                    updated_at  = ?
                WHERE job_id      = ?
                  AND lease_owner = ?
                """,
                (_now(), job_id, worker_id),
            )

        self._LOG.info(
            "FAIL | job_id=%s worker_id=%s",
            job_id,
            worker_id,
        )
        return self.get(job_id)

    def get(self, job_id: str) -> QueueJob:
        """
        Retrieves a job by ID.
        Raises JobNotFoundError if not found.
        """
        row = self._read_one(
            "SELECT * FROM worker_jobs WHERE job_id = ?",
            (job_id,),
        )
        if row is None:
            raise JobNotFoundError(f"Job '{job_id}' not found in worker queue.")
        return self._record(row)

    def list_by_queue(
        self,
        queue: str,
        status: str | None = None,
    ) -> list[QueueJob]:
        """Returns all jobs in a queue, optionally filtered by status."""
        if status:
            rows = self._read(
                """
                SELECT * FROM worker_jobs
                WHERE queue = ? AND status = ?
                ORDER BY updated_at ASC
                """,
                (queue, status),
            )
        else:
            rows = self._read(
                """
                SELECT * FROM worker_jobs
                WHERE queue = ?
                ORDER BY updated_at ASC
                """,
                (queue,),
            )
        return [self._record(r) for r in rows]

    def queue_depth(self, queue: str, status: str = "pending") -> int:
        """Returns the count of jobs in the given queue and status."""
        row = self._read_one(
            "SELECT COUNT(*) AS cnt FROM worker_jobs WHERE queue = ? AND status = ?",
            (queue, status),
        )
        return cast(Any, row)["cnt"] if row else 0

    # ── Internal helpers ──────────────────────────────────────────────

    def _assert_ownership(
        self,
        job_id: str,
        worker_id: str,
        expected_status: str,
    ) -> QueueJob:
        """
        Fetches the job and validates worker ownership and expected status.
        Raises JobNotFoundError, JobOwnershipError, or InvalidStatusTransitionError.
        """
        job = self.get(job_id)

        if job.lease_owner != worker_id:
            raise JobOwnershipError(
                f"Worker '{worker_id}' does not own the lease for job '{job_id}'. "
                f"Current owner: '{job.lease_owner}'."
            )

        if job.status != expected_status:
            raise InvalidStatusTransitionError(
                f"Job '{job_id}' is in status '{job.status}', expected '{expected_status}'."
            )

        return job

    @staticmethod
    def _record(row: sqlite3.Row) -> QueueJob:
        return QueueJob(
            job_id=row["job_id"],
            queue=row["queue"],
            payload=json.loads(row["payload"]),
            attempts=row["attempts"],
            lease_owner=row["lease_owner"],
            status=row["status"],
            updated_at=row["updated_at"],
        )


# =====================================================================
# INTEGRATION SMOKE TEST
# =====================================================================
def _run_integration_test() -> None:
    """
    End-to-end smoke test for SQLiteExecutionStore and SQLiteWorkerQueue.

    Covers:
        Store:  create → checkpoint → complete → fail → duplicate guard → status list
        Queue:  enqueue → claim → retry → acknowledge → fail_job →
                ownership guard → duplicate guard → depth → list
    """
    logger.info("=" * 60)
    logger.info("OIS Persistence Layer — Integration Smoke Test")
    logger.info("=" * 60)

    store = SQLiteExecutionStore(":memory:")
    queue = SQLiteWorkerQueue(":memory:")

    # ── Execution Store Tests ──────────────────────────────────────────

    # Test 1: Create execution
    rec = store.create(
        execution_id="exec_001",
        workflow_id="wf_content_publish",
        payload={"brand_id": "brand_01", "platform": "tiktok"},
    )
    assert rec.status == "ready", f"Expected 'ready', got '{rec.status}'"
    assert rec.checkpoint is None
    logger.info("STORE TEST 1 PASSED | create execution_id=exec_001 status=ready")

    # Test 2: Checkpoint
    rec = store.checkpoint(
        "exec_001",
        checkpoint={"step": "hook_generation", "hook": "Stop saving money."},
    )
    assert rec.status == "running"
    assert rec.checkpoint is not None
    assert rec.checkpoint["step"] == "hook_generation"
    logger.info("STORE TEST 2 PASSED | checkpoint status=running checkpoint persisted")

    # Test 3: Complete
    rec = store.complete("exec_001", result={"publish_id": "pub_abc123"})
    assert rec.status == "succeeded"
    assert rec.result == {"publish_id": "pub_abc123"}
    logger.info("STORE TEST 3 PASSED | complete status=succeeded result present")

    # Test 4: Invalid terminal re-transition
    try:
        store.complete("exec_001", result={"publish_id": "pub_again"})
        raise AssertionError("Should have raised InvalidStatusTransitionError")
    except InvalidStatusTransitionError:
        logger.info("STORE TEST 4 PASSED | terminal re-transition correctly blocked")

    # Test 5: Fail path
    rec_f = store.create(
        execution_id="exec_002",
        workflow_id="wf_content_publish",
        payload={"brand_id": "brand_02", "platform": "instagram"},
    )
    store.checkpoint("exec_002", checkpoint={"step": "caption_generation"})
    rec_f = store.fail(
        "exec_002",
        error={"code": "TOOL_TIMEOUT", "message": "TikTok API did not respond."},
    )
    assert rec_f.status == "failed"
    assert rec_f.error is not None
    assert rec_f.error["code"] == "TOOL_TIMEOUT"
    logger.info("STORE TEST 5 PASSED | fail status=failed error payload present")

    # Test 6: Duplicate execution guard
    try:
        store.create(
            execution_id="exec_001",
            workflow_id="wf_duplicate",
            payload={},
        )
        raise AssertionError("Should have raised DuplicateExecutionError")
    except DuplicateExecutionError:
        logger.info("STORE TEST 6 PASSED | duplicate execution_id correctly blocked")

    # Test 7: list_by_status
    succeeded = store.list_by_status("succeeded")
    assert any(r.execution_id == "exec_001" for r in succeeded)
    logger.info("STORE TEST 7 PASSED | list_by_status returned correct records")

    # ── Worker Queue Tests ─────────────────────────────────────────────

    # Test 8: Enqueue
    job = queue.enqueue(
        job_id="job_001",
        queue="content_publish",
        payload={"content_id": "cnt_xyz", "platform": "tiktok"},
    )
    assert job.status == "pending"
    assert job.attempts == 0
    logger.info("QUEUE TEST 8 PASSED | enqueue job_id=job_001 status=pending")

    # Test 9: Claim
    claimed = queue.claim(queue="content_publish", worker_id="worker_A")
    assert claimed is not None
    assert claimed.job_id == "job_001"
    assert claimed.status == "leased"
    assert claimed.lease_owner == "worker_A"
    logger.info("QUEUE TEST 9 PASSED | claim job_id=job_001 lease_owner=worker_A")

    # Test 10: No double-claim
    second_claim = queue.claim(queue="content_publish", worker_id="worker_B")
    assert second_claim is None, "Already-leased job should not be claimable"
    logger.info("QUEUE TEST 10 PASSED | double-claim correctly blocked")

    # Test 11: Retry
    retried = queue.retry(job_id="job_001", worker_id="worker_A")
    assert retried.status == "pending"
    assert retried.lease_owner is None
    assert retried.attempts == 1
    logger.info("QUEUE TEST 11 PASSED | retry status=pending attempts=1")

    # Test 12: Ownership guard on retry
    queue.claim(queue="content_publish", worker_id="worker_A")
    try:
        queue.retry(job_id="job_001", worker_id="worker_B")
        raise AssertionError("Should have raised JobOwnershipError")
    except JobOwnershipError:
        logger.info("QUEUE TEST 12 PASSED | ownership guard correctly enforced on retry")

    # Test 13: Acknowledge
    acked = queue.acknowledge(job_id="job_001", worker_id="worker_A")
    assert acked.status == "completed"
    logger.info("QUEUE TEST 13 PASSED | acknowledge status=completed")

    # Test 14: Fail job terminal path
    queue.enqueue("job_002", "content_publish", {"content_id": "cnt_zzz"})
    queue.claim(queue="content_publish", worker_id="worker_A")
    failed_job = queue.fail_job(job_id="job_002", worker_id="worker_A")
    assert failed_job.status == "failed"
    logger.info("QUEUE TEST 14 PASSED | fail_job status=failed")

    # Test 15: Duplicate job guard
    try:
        queue.enqueue("job_001", "content_publish", {})
        raise AssertionError("Should have raised DuplicateJobError")
    except DuplicateJobError:
        logger.info("QUEUE TEST 15 PASSED | duplicate job_id correctly blocked")

    # Test 16: Queue depth
    queue.enqueue("job_003", "content_publish", {"x": 1})
    queue.enqueue("job_004", "content_publish", {"x": 2})
    depth = queue.queue_depth("content_publish", status="pending")
    assert depth == 2, f"Expected depth=2, got {depth}"
    logger.info("QUEUE TEST 16 PASSED | queue_depth=2 for pending jobs")

    # Test 17: List by queue and status
    pending_jobs = queue.list_by_queue("content_publish", status="pending")
    assert len(pending_jobs) == 2
    logger.info(
        "QUEUE TEST 17 PASSED | list_by_queue returned %d pending jobs",
        len(pending_jobs),
    )

    logger.info("=" * 60)
    logger.info("ALL 17 TESTS PASSED | OIS Persistence Layer v3.0.0 verified")
    logger.info("=" * 60)

    store.close()
    queue.close()


if __name__ == "__main__":
    _run_integration_test()

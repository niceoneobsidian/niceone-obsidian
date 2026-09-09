"""Lease-based distributed worker runtime primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class WorkItem:
    work_id: str
    payload: dict[str, Any]
    attempts: int = 0
    status: str = "QUEUED"
    worker_id: str | None = None
    lease_until: datetime | None = None
    result: Any = None
    error: str | None = None


class LeaseQueue:
    """Thread-safe queue with exclusive leases and expiry recovery."""

    def __init__(self, lease_seconds: int = 30, max_attempts: int = 3) -> None:
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self._items: dict[str, WorkItem] = {}
        self._lock = Lock()

    def enqueue(self, payload: dict[str, Any]) -> str:
        with self._lock:
            item = WorkItem(str(uuid4()), dict(payload))
            self._items[item.work_id] = item
            return item.work_id

    def claim(self, worker_id: str) -> WorkItem | None:
        with self._lock:
            self._expire_locked()
            for item in self._items.values():
                if item.status == "QUEUED" and item.attempts < self.max_attempts:
                    item.status = "RUNNING"
                    item.worker_id = worker_id
                    item.attempts += 1
                    item.lease_until = _now() + timedelta(seconds=self.lease_seconds)
                    return item
            return None

    def heartbeat(self, work_id: str, worker_id: str) -> bool:
        with self._lock:
            item = self._items.get(work_id)
            if not item or item.status != "RUNNING" or item.worker_id != worker_id:
                return False
            item.lease_until = _now() + timedelta(seconds=self.lease_seconds)
            return True

    def complete(self, work_id: str, worker_id: str, result: Any) -> bool:
        with self._lock:
            item = self._items.get(work_id)
            if not item or item.status != "RUNNING" or item.worker_id != worker_id:
                return False
            item.status, item.result, item.lease_until = "SUCCEEDED", result, None
            return True

    def fail(self, work_id: str, worker_id: str, error: str) -> bool:
        with self._lock:
            item = self._items.get(work_id)
            if not item or item.status != "RUNNING" or item.worker_id != worker_id:
                return False
            item.error, item.lease_until = error, None
            item.status = "QUEUED" if item.attempts < self.max_attempts else "FAILED"
            return True

    def recover_expired(self) -> int:
        with self._lock:
            return self._expire_locked()

    def _expire_locked(self) -> int:
        count = 0
        now = _now()
        for item in self._items.values():
            if item.status == "RUNNING" and item.lease_until and item.lease_until <= now:
                item.status = "QUEUED" if item.attempts < self.max_attempts else "FAILED"
                item.worker_id = None
                item.lease_until = None
                count += 1
        return count

    def get(self, work_id: str) -> WorkItem | None:
        with self._lock:
            return self._items.get(work_id)


class Worker:
    def __init__(
        self, worker_id: str, queue: LeaseQueue, handler: Callable[[dict[str, Any]], Any]
    ) -> None:
        self.worker_id, self.queue, self.handler = worker_id, queue, handler

    def run_once(self) -> bool:
        item = self.queue.claim(self.worker_id)
        if item is None:
            return False
        try:
            result = self.handler(item.payload)
        except Exception as exc:  # recovery boundary intentionally catches task failures
            self.queue.fail(item.work_id, self.worker_id, str(exc))
        else:
            self.queue.complete(item.work_id, self.worker_id, result)
        return True

"""Production-oriented polling scheduler over existing polling adapters."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from time import monotonic, sleep

from ois.infrastructure.source_adapters.base import AdapterResult, SourceAdapter
from ois.infrastructure.source_gateway import SourceGateway


@dataclass(frozen=True)
class PollingJob:
    source_id: str
    interval_seconds: float
    adapter: SourceAdapter
    tenant_id: str
    workspace_id: str
    credential_id: str | None = None

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("poll interval must be positive")


@dataclass(frozen=True)
class PollingRun:
    source_id: str
    started_at: float
    completed_at: float
    result: AdapterResult | None = None
    error: str | None = None


class PollingEngine:
    """Bounded concurrent poll scheduler.

    Cursor durability remains owned by PollingSourceAdapter/SQLiteCursorStore;
    this engine only schedules work and never advances a cursor itself.
    """

    def __init__(
        self,
        *,
        gateway: SourceGateway,
        jobs: tuple[PollingJob, ...] = (),
        max_workers: int = 4,
        clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")
        self._gateway = gateway
        self._jobs: dict[str, PollingJob] = {job.source_id: job for job in jobs}
        self._max_workers = max_workers
        self._clock = clock
        self._sleep = sleeper
        self._next_due: dict[str, float] = {}

    def register(self, job: PollingJob) -> None:
        if job.source_id in self._jobs:
            raise ValueError(f"polling job already registered: {job.source_id}")
        self._jobs[job.source_id] = job

    def unregister(self, source_id: str) -> None:
        if source_id not in self._jobs:
            raise KeyError(f"polling job not registered: {source_id}")
        del self._jobs[source_id]
        self._next_due.pop(source_id, None)

    def run_once(self, source_id: str) -> PollingRun:
        job = self._jobs[source_id]
        started = self._clock()
        try:
            result = job.adapter.ingest(
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
                gateway=self._gateway,
                credential_id=job.credential_id,
            )
            return PollingRun(source_id, started, self._clock(), result=result)
        except Exception as exc:  # noqa: BLE001 - scheduler records connector failures
            return PollingRun(
                source_id, started, self._clock(), error=f"{type(exc).__name__}: {exc}"
            )

    def due_sources(self) -> tuple[str, ...]:
        now = self._clock()
        return tuple(
            sorted(
                source_id
                for source_id, job in self._jobs.items()
                if self._next_due.get(source_id, 0.0) <= now
            )
        )

    def run_due(self) -> tuple[PollingRun, ...]:
        due = self.due_sources()
        if not due:
            return ()
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures: dict[str, Future[PollingRun]] = {
                source_id: executor.submit(self.run_once, source_id) for source_id in due
            }
            runs = tuple(futures[source_id].result() for source_id in due)
        now = self._clock()
        for run in runs:
            job = self._jobs.get(run.source_id)
            if job is None:
                continue
            # Failed jobs retry on the next interval; successful jobs are also
            # scheduled from completion time, avoiding tight failure loops.
            self._next_due[run.source_id] = now + job.interval_seconds
        return runs

    def run_forever(self, *, stop: Callable[[], bool]) -> None:
        while not stop():
            runs = self.run_due()
            if runs:
                continue
            self._sleep(0.25)

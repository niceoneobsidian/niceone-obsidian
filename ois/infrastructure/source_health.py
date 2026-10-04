"""Source health snapshots and lifecycle-aware observability primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock


@dataclass(frozen=True)
class SourceHealthSnapshot:
    source_id: str
    tenant_id: str
    workspace_id: str
    healthy: bool
    checked_at: datetime
    latency_ms: float | None = None
    consecutive_failures: int = 0
    last_error: str | None = None

    @property
    def state(self) -> str:
        return "healthy" if self.healthy else "degraded"


class SourceHealthRegistry:
    """Thread-safe in-process health state; durable telemetry can consume snapshots."""

    def __init__(self) -> None:
        self._snapshots: dict[tuple[str, str, str], SourceHealthSnapshot] = {}
        self._lock = RLock()

    def record(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
        healthy: bool,
        latency_ms: float | None = None,
        error: str | None = None,
        checked_at: datetime | None = None,
    ) -> SourceHealthSnapshot:
        key = (tenant_id, workspace_id, source_id)
        with self._lock:
            previous = self._snapshots.get(key)
            failures = 0 if healthy else (previous.consecutive_failures + 1 if previous else 1)
            snapshot = SourceHealthSnapshot(
                source_id=source_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                healthy=healthy,
                checked_at=checked_at or datetime.now(UTC),
                latency_ms=latency_ms,
                consecutive_failures=failures,
                last_error=None if healthy else error,
            )
            self._snapshots[key] = snapshot
            return snapshot

    def get(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
    ) -> SourceHealthSnapshot | None:
        with self._lock:
            return self._snapshots.get((tenant_id, workspace_id, source_id))

    def list(self, *, tenant_id: str, workspace_id: str) -> tuple[SourceHealthSnapshot, ...]:
        with self._lock:
            return tuple(
                self._snapshots[key]
                for key in sorted(self._snapshots)
                if key[:2] == (tenant_id, workspace_id)
            )

    def clear(self, *, tenant_id: str, workspace_id: str, source_id: str) -> None:
        with self._lock:
            self._snapshots.pop((tenant_id, workspace_id, source_id), None)

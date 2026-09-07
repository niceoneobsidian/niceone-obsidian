"""Append-only analytics and social event metrics storage."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MetricObservation:
    observation_id: str
    entity_id: str
    metric: str
    value: float
    observed_at: datetime
    platform: str | None = None
    source_event_id: str | None = None


class SQLiteAnalyticsStore:
    """Reference analytics store; production deployments can use PostgreSQL."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._db = sqlite3.connect(str(path))
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS metric_observations (
                observation_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL,
                metric TEXT NOT NULL, value REAL NOT NULL,
                observed_at TEXT NOT NULL, platform TEXT, source_event_id TEXT
            )"""
        )
        self._db.commit()

    def append(self, observation: MetricObservation) -> bool:
        row = asdict(observation)
        row["observed_at"] = observation.observed_at.isoformat()
        cursor = self._db.execute(
            """INSERT OR IGNORE INTO metric_observations
            (observation_id, entity_id, metric, value, observed_at, platform, source_event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            tuple(row.values()),
        )
        self._db.commit()
        return cursor.rowcount == 1

    def record_event_metrics(self, event: Any) -> int:
        return sum(
            self.append(
                MetricObservation(
                    observation_id=f"{event.event_id}:{metric}",
                    entity_id=event.external_id or event.event_id,
                    metric=str(metric),
                    value=float(value),
                    observed_at=event.occurred_at,
                    platform=event.platform,
                    source_event_id=event.event_id,
                )
            )
            for metric, value in event.metrics.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        )

    def latest(self, entity_id: str, metric: str) -> MetricObservation | None:
        row = self._db.execute(
            "SELECT * FROM metric_observations WHERE entity_id=? AND metric=? "
            "ORDER BY observed_at DESC LIMIT 1",
            (entity_id, metric),
        ).fetchone()
        if row is None:
            return None
        return MetricObservation(
            observation_id=row["observation_id"],
            entity_id=row["entity_id"],
            metric=row["metric"],
            value=float(row["value"]),
            observed_at=datetime.fromisoformat(row["observed_at"]),
            platform=row["platform"],
            source_event_id=row["source_event_id"],
        )

    def close(self) -> None:
        self._db.close()

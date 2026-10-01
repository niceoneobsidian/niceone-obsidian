"""Durable prediction/outcome ledger and empirical calibration for G2."""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PredictionSnapshot:
    prediction_id: str
    content_id: str
    model_id: str
    model_version: str
    metrics: dict[str, float]
    confidence: float
    predicted_at: datetime


@dataclass(frozen=True)
class OutcomeEvent:
    outcome_id: str
    content_id: str
    metric: str
    value: float
    observed_at: datetime
    window: str
    source: str


@dataclass(frozen=True)
class CalibrationReport:
    sample_count: int
    mae: float
    rmse: float
    mean_confidence: float
    bins: tuple[dict[str, float], ...]


class OutcomeLedger:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                content_id TEXT,
                model_id TEXT,
                model_version TEXT,
                metrics TEXT,
                confidence REAL,
                predicted_at TEXT
            );
            CREATE TABLE IF NOT EXISTS outcomes (
                outcome_id TEXT PRIMARY KEY,
                content_id TEXT,
                metric TEXT,
                value REAL,
                observed_at TEXT,
                window TEXT,
                source TEXT
            );
            """
        )
        self._db.commit()

    def record_prediction(self, prediction: PredictionSnapshot) -> bool:
        cursor = self._db.execute(
            "INSERT OR IGNORE INTO predictions VALUES(?,?,?,?,?,?,?)",
            (
                prediction.prediction_id,
                prediction.content_id,
                prediction.model_id,
                prediction.model_version,
                json.dumps(prediction.metrics),
                prediction.confidence,
                prediction.predicted_at.isoformat(),
            ),
        )
        self._db.commit()
        return cursor.rowcount == 1

    def record_outcome(self, outcome: OutcomeEvent) -> bool:
        cursor = self._db.execute(
            "INSERT OR IGNORE INTO outcomes VALUES(?,?,?,?,?,?,?)",
            (
                outcome.outcome_id,
                outcome.content_id,
                outcome.metric,
                outcome.value,
                outcome.observed_at.isoformat(),
                outcome.window,
                outcome.source,
            ),
        )
        self._db.commit()
        return cursor.rowcount == 1

    def calibrate(self, *, metric: str, bins: int = 10) -> CalibrationReport:
        rows = self._db.execute(
            """
            SELECT p.metrics, o.value, p.confidence
            FROM predictions p
            JOIN outcomes o ON p.content_id = o.content_id
            WHERE o.metric = ?
            """,
            (metric,),
        ).fetchall()
        pairs: list[tuple[float, float, float]] = []
        for row in rows:
            predicted = json.loads(row["metrics"]).get(metric)
            if isinstance(predicted, int | float):
                pairs.append((float(predicted), float(row["value"]), float(row["confidence"])))
        if not pairs:
            return CalibrationReport(0, 0.0, 0.0, 0.0, ())

        errors = [predicted - observed for predicted, observed, _ in pairs]
        mae = sum(abs(error) for error in errors) / len(errors)
        rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
        buckets: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
        for predicted, observed, confidence in pairs:
            index = min(bins - 1, int(confidence * bins))
            buckets[index].append((predicted, observed))

        report = tuple(
            {
                "lower": index / bins,
                "upper": (index + 1) / bins,
                "predicted": sum(predicted for predicted, _ in bucket) / len(bucket),
                "actual": sum(observed for _, observed in bucket) / len(bucket),
                "count": float(len(bucket)),
            }
            for index, bucket in enumerate(buckets)
            if bucket
        )
        mean_confidence = sum(confidence for _, _, confidence in pairs) / len(pairs)
        return CalibrationReport(len(pairs), mae, rmse, mean_confidence, report)

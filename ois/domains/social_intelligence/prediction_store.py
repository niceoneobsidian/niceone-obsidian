"""Durable G2 prediction/outcome dataset and calibration evaluation."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ois.domains.social_intelligence.learning import PerformanceObservation
from ois.domains.social_intelligence.prediction import Prediction


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    count: int
    predicted_mean: float
    observed_mean: float
    absolute_error: float


@dataclass(frozen=True)
class CalibrationReport:
    metric: str
    sample_count: int
    mean_absolute_error: float
    bins: tuple[CalibrationBin, ...]


class PredictionDataset:
    """Append-only prediction/outcome dataset with deterministic evaluation."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path))
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_key TEXT PRIMARY KEY,
                content_id TEXT NOT NULL,
                model_version TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS outcomes (
                outcome_key TEXT PRIMARY KEY,
                content_id TEXT NOT NULL,
                source TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def record_prediction(self, prediction: Prediction) -> str:
        key = f"{prediction.content_id}:{prediction.model_id}:{prediction.model_version}"
        self._connection.execute(
            "INSERT OR REPLACE INTO predictions VALUES (?, ?, ?, ?)",
            (
                key,
                prediction.content_id,
                prediction.model_version,
                json.dumps(
                    {
                        "metrics": dict(prediction.metrics),
                        "confidence": prediction.confidence,
                        "evidence": list(prediction.evidence),
                    },
                    sort_keys=True,
                ),
            ),
        )
        self._connection.commit()
        return key

    def record_outcome(self, outcome: PerformanceObservation) -> str:
        key = f"{outcome.content_id}:{outcome.source}:{outcome.observed_at}"
        self._connection.execute(
            "INSERT OR REPLACE INTO outcomes VALUES (?, ?, ?, ?, ?)",
            (
                key,
                outcome.content_id,
                outcome.source,
                outcome.observed_at,
                json.dumps(dict(outcome.metrics), sort_keys=True),
            ),
        )
        self._connection.commit()
        return key

    def paired(self, *, metric: str) -> list[tuple[float, float]]:
        rows = self._connection.execute(
            """
            SELECT p.payload AS prediction, o.payload AS outcome
            FROM predictions p
            JOIN outcomes o ON p.content_id = o.content_id
            ORDER BY o.observed_at
            """
        ).fetchall()
        pairs: list[tuple[float, float]] = []
        for row in rows:
            predicted = json.loads(row["prediction"])["metrics"].get(metric)
            observed = json.loads(row["outcome"]).get(metric)
            if isinstance(predicted, int | float) and isinstance(
                observed, int | float
            ):
                pairs.append((float(predicted), float(observed)))
        return pairs

    def calibration(self, *, metric: str, bins: int = 10) -> CalibrationReport:
        if bins <= 0:
            raise ValueError("bins must be positive")
        pairs = self.paired(metric=metric)
        if not pairs:
            return CalibrationReport(metric, 0, 0.0, ())

        width = 1.0 / bins
        result: list[CalibrationBin] = []
        for index in range(bins):
            lower = index * width
            upper = 1.0 if index == bins - 1 else (index + 1) * width
            selected = [
                (predicted, observed)
                for predicted, observed in pairs
                if lower <= predicted <= upper
                and (index == bins - 1 or predicted < upper)
            ]
            if not selected:
                continue
            predicted_mean = sum(item[0] for item in selected) / len(selected)
            observed_mean = sum(item[1] for item in selected) / len(selected)
            result.append(
                CalibrationBin(
                    lower=lower,
                    upper=upper,
                    count=len(selected),
                    predicted_mean=predicted_mean,
                    observed_mean=observed_mean,
                    absolute_error=abs(predicted_mean - observed_mean),
                )
            )

        mae = (
            sum(abs(predicted - observed) for predicted, observed in pairs) / len(pairs)
        )
        return CalibrationReport(metric, len(pairs), mae, tuple(result))

    def close(self) -> None:
        self._connection.close()

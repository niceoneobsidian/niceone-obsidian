"""PostgreSQL persistence adapters for metrics and attribution."""

from __future__ import annotations

from typing import Any

from .analytics_store import MetricObservation
from .attribution import AttributionResult


class PostgreSQLSocialAnalytics:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def append_metric(self, observation: MetricObservation) -> bool:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO social_metric_observations
                (observation_id, entity_id, metric, value, observed_at, platform, source_event_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (observation_id) DO NOTHING""",
                (
                    observation.observation_id,
                    observation.entity_id,
                    observation.metric,
                    observation.value,
                    observation.observed_at,
                    observation.platform,
                    observation.source_event_id,
                ),
            )
            inserted = cursor.rowcount == 1
        self._connection.commit()
        return inserted  # type: ignore

    def append_attribution(self, result: AttributionResult) -> int:
        inserted = 0
        with self._connection.cursor() as cursor:
            for touchpoint_id, credit in result.credited_touchpoints:
                cursor.execute(
                    """INSERT INTO social_attribution_results
                    (conversion_id, touchpoint_id, credit, total_value, confidence)
                    VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (
                        result.conversion_id,
                        touchpoint_id,
                        credit,
                        result.total_value,
                        result.confidence,
                    ),
                )
                inserted += int(cursor.rowcount == 1)
        self._connection.commit()
        return inserted

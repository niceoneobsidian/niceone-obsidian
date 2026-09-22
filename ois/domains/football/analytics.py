from __future__ import annotations

from collections.abc import Iterable, Mapping
import importlib
from typing import Any

from .models import FootballStatistic


def statistics_records(statistics: Iterable[FootballStatistic]) -> list[dict[str, Any]]:
    return [
        {
            "entity_id": item.entity_id,
            "metric": item.metric,
            "value": item.value,
            "scope": item.scope,
            "provider": item.provider,
            "observed_at": item.observed_at,
        }
        for item in statistics
    ]


def records_to_dataframe(records: Iterable[Mapping[str, Any]]) -> Any:
    """Return a pandas DataFrame when the optional analytics dependency is installed."""
    try:
        pd = importlib.import_module("pandas")
    except ImportError as exc:
        raise RuntimeError("Install pandas to use the OIS football DataFrame interface.") from exc
    return pd.DataFrame(list(records))


def summarize_statistics(statistics: Iterable[FootballStatistic]) -> dict[str, dict[str, float]]:
    """Simple provider-neutral descriptive statistics without forcing pandas."""
    buckets: dict[str, list[float]] = {}
    for statistic in statistics:
        if isinstance(statistic.value, bool) or not isinstance(statistic.value, (int, float)):
            continue
        buckets.setdefault(statistic.metric, []).append(float(statistic.value))

    return {
        metric: {
            "count": float(len(values)),
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }
        for metric, values in buckets.items()
        if values
    }

"""Attribution primitives for market performance."""

from __future__ import annotations

from collections import defaultdict

from .schemas import MarketEvaluation


def attribute_by_prediction_version(
    evaluations: list[MarketEvaluation],
) -> dict[str, dict[str, float | int]]:
    """Group observed market performance by upstream prediction version."""
    groups: dict[str, list[MarketEvaluation]] = defaultdict(list)
    for evaluation in evaluations:
        groups[evaluation.prediction_version].append(evaluation)

    result: dict[str, dict[str, float | int]] = {}
    for version, items in groups.items():
        decided = [item for item in items if item.correct is not None]
        roi = [item.roi_if_staked for item in items if item.roi_if_staked is not None]
        result[version] = {
            "count": len(items),
            "accuracy": sum(bool(item.correct) for item in decided) / len(decided)
            if decided
            else 0.0,
            "mean_edge": sum(item.edge for item in items) / len(items) if items else 0.0,
            "roi_sum": sum(roi),
        }
    return result

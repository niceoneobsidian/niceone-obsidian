"""Market evaluation metrics."""

from __future__ import annotations

from .schemas import MarketEvaluation, MarketEvent, MarketOutcome, OutcomeStatus


def evaluate_market_event(event: MarketEvent, outcome: MarketOutcome) -> MarketEvaluation:
    """Create a point-in-time, auditable evaluation from prediction + settlement."""
    if event.event_id != outcome.event_id:
        raise ValueError("Market event and outcome IDs must match")

    correct: bool | None
    roi: float | None
    if outcome.status is OutcomeStatus.WIN:
        correct, roi = True, event.odds - 1.0
    elif outcome.status is OutcomeStatus.LOSS:
        correct, roi = False, -1.0
    elif outcome.status in {OutcomeStatus.PUSH, OutcomeStatus.VOID}:
        correct, roi = None, 0.0
    else:
        correct, roi = None, None

    return MarketEvaluation(
        event_id=event.event_id,
        match_id=event.match_id,
        status=outcome.status,
        correct=correct,
        model_probability=event.model_probability,
        implied_probability=event.implied_probability,
        edge=event.model_probability - event.implied_probability,
        odds=event.odds,
        roi_if_staked=roi,
        prediction_id=event.prediction_id,
        prediction_version=event.prediction_version,
    )


def aggregate_market_evaluations(evaluations: list[MarketEvaluation]) -> dict[str, float | int]:
    """Return stable aggregate metrics without pretending they prove future edge."""
    settled = [
        e
        for e in evaluations
        if e.status in {OutcomeStatus.WIN, OutcomeStatus.LOSS, OutcomeStatus.PUSH}
    ]
    decided = [e for e in settled if e.correct is not None]
    roi_values = [e.roi_if_staked for e in settled if e.roi_if_staked is not None]
    return {
        "count": len(evaluations),
        "settled_count": len(settled),
        "decided_count": len(decided),
        "accuracy": sum(bool(e.correct) for e in decided) / len(decided) if decided else 0.0,
        "mean_edge": sum(e.edge for e in settled) / len(settled) if settled else 0.0,
        "roi_sum": sum(roi_values),
        "roi_mean": sum(roi_values) / len(roi_values) if roi_values else 0.0,
    }

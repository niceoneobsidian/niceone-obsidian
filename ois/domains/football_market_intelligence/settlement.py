"""Deterministic settlement for canonical football markets."""

from __future__ import annotations

from .markets import MarketType, Selection
from .schemas import MarketEvent, MarketOutcome, OutcomeStatus


def settle_market(event: MarketEvent, home_goals: int, away_goals: int) -> MarketOutcome:
    """Settle an event from final score only.

    SPECIAL 1UP uses the OIS reference definition: the selected team finishes
    at least one goal ahead. Bookmaker-specific early-payout semantics are not
    inferred here and require a dedicated licensed market adapter.
    """
    if home_goals < 0 or away_goals < 0:
        raise ValueError("Goals cannot be negative")

    total = home_goals + away_goals
    margin = home_goals - away_goals
    line = event.line
    selected_value: float

    if event.market_type is MarketType.RESULT:
        selected_value = {Selection.HOME_WIN: 1, Selection.DRAW: 0, Selection.AWAY_WIN: -1}[event.selection]
        actual = 1 if margin > 0 else 0 if margin == 0 else -1
        status = OutcomeStatus.WIN if actual == selected_value else OutcomeStatus.LOSS
    elif event.market_type is MarketType.DOUBLE_CHANCE:
        actual = {Selection.HOME_OR_DRAW: margin >= 0, Selection.DRAW_OR_AWAY: margin <= 0, Selection.HOME_OR_AWAY: margin != 0}[event.selection]
        status = OutcomeStatus.WIN if actual else OutcomeStatus.LOSS
    elif event.market_type is MarketType.TOTAL_GOALS:
        assert line is not None
        status = _over_under_status(total, line, event.selection)
    elif event.market_type is MarketType.TEAM_GOALS:
        assert line is not None
        value = home_goals if event.selection in {Selection.HOME_OVER, Selection.HOME_UNDER} else away_goals
        selection = Selection.OVER if event.selection in {Selection.HOME_OVER, Selection.AWAY_OVER} else Selection.UNDER
        status = _over_under_status(value, line, selection)
    elif event.market_type is MarketType.BTTS:
        btts = home_goals > 0 and away_goals > 0
        expected = event.selection is Selection.BTTS_YES
        status = OutcomeStatus.WIN if btts == expected else OutcomeStatus.LOSS
    elif event.market_type is MarketType.HANDICAP:
        assert line is not None
        adjusted = margin + line if event.selection is Selection.HOME_HANDICAP else -margin + line
        status = OutcomeStatus.WIN if adjusted > 0 else OutcomeStatus.LOSS if adjusted < 0 else OutcomeStatus.PUSH
    elif event.market_type is MarketType.SPECIAL:
        if event.selection is Selection.HOME_1UP:
            status = OutcomeStatus.WIN if margin >= 1 else OutcomeStatus.LOSS
        else:
            status = OutcomeStatus.WIN if margin <= -1 else OutcomeStatus.LOSS
    else:
        raise ValueError(f"Unsupported market type: {event.market_type}")

    return MarketOutcome(event_id=event.event_id, status=status, actual_value=float(total))


def _over_under_status(value: float, line: float, selection: Selection) -> OutcomeStatus:
    if value == line:
        return OutcomeStatus.PUSH
    is_over = value > line
    wants_over = selection is Selection.OVER
    return OutcomeStatus.WIN if is_over == wants_over else OutcomeStatus.LOSS

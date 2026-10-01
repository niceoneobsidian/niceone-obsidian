"""Canonical football market taxonomy and validation helpers."""

from __future__ import annotations

from enum import StrEnum


class MarketType(StrEnum):
    """Supported deterministic football market families."""

    RESULT = "result"
    DOUBLE_CHANCE = "double_chance"
    TOTAL_GOALS = "total_goals"
    TEAM_GOALS = "team_goals"
    BTTS = "btts"
    HANDICAP = "handicap"
    SPECIAL = "special"


class Selection(StrEnum):
    HOME_WIN = "home_win"
    DRAW = "draw"
    AWAY_WIN = "away_win"
    HOME_OR_DRAW = "1x"
    DRAW_OR_AWAY = "x2"
    HOME_OR_AWAY = "12"
    OVER = "over"
    UNDER = "under"
    HOME_OVER = "home_over"
    HOME_UNDER = "home_under"
    AWAY_OVER = "away_over"
    AWAY_UNDER = "away_under"
    BTTS_YES = "btts_yes"
    BTTS_NO = "btts_no"
    HOME_HANDICAP = "home_handicap"
    AWAY_HANDICAP = "away_handicap"
    HOME_1UP = "home_1up"
    AWAY_1UP = "away_1up"


RESULT_SELECTIONS = {
    Selection.HOME_WIN,
    Selection.DRAW,
    Selection.AWAY_WIN,
}
DOUBLE_CHANCE_SELECTIONS = {
    Selection.HOME_OR_DRAW,
    Selection.DRAW_OR_AWAY,
    Selection.HOME_OR_AWAY,
}
TOTAL_SELECTIONS = {Selection.OVER, Selection.UNDER}
TEAM_GOAL_SELECTIONS = {
    Selection.HOME_OVER,
    Selection.HOME_UNDER,
    Selection.AWAY_OVER,
    Selection.AWAY_UNDER,
}
BTTS_SELECTIONS = {Selection.BTTS_YES, Selection.BTTS_NO}
HANDICAP_SELECTIONS = {Selection.HOME_HANDICAP, Selection.AWAY_HANDICAP}
SPECIAL_SELECTIONS = {Selection.HOME_1UP, Selection.AWAY_1UP}


def validate_market_selection(market_type: MarketType, selection: Selection) -> None:
    """Reject combinations that cannot be deterministically interpreted."""
    allowed = {
        MarketType.RESULT: RESULT_SELECTIONS,
        MarketType.DOUBLE_CHANCE: DOUBLE_CHANCE_SELECTIONS,
        MarketType.TOTAL_GOALS: TOTAL_SELECTIONS,
        MarketType.TEAM_GOALS: TEAM_GOAL_SELECTIONS,
        MarketType.BTTS: BTTS_SELECTIONS,
        MarketType.HANDICAP: HANDICAP_SELECTIONS,
        MarketType.SPECIAL: SPECIAL_SELECTIONS,
    }[market_type]
    if selection not in allowed:
        raise ValueError(f"Selection {selection.value!r} is invalid for {market_type.value!r}")

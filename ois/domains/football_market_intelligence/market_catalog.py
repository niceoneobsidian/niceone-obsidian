"""Canonical football market catalog and bookmaker normalization.

The catalog is deliberately broader than the deterministic MarketEvent settlement
families. Provider feeds can expose dynamic selections and lines without requiring
a code change for every bookmaker-specific outcome label.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MarketFamily(StrEnum):
    RESULT = "result"
    DOUBLE_CHANCE = "double_chance"
    DRAW_NO_BET = "draw_no_bet"
    HANDICAP = "handicap"
    ASIAN_HANDICAP = "asian_handicap"
    TOTAL_GOALS = "total_goals"
    TEAM_TOTAL_GOALS = "team_total_goals"
    BTTS = "btts"
    CORRECT_SCORE = "correct_score"
    EXACT_GOALS = "exact_goals"
    HALF_TIME = "half_time"
    HALF_TIME_FULL_TIME = "half_time_full_time"
    CORNERS = "corners"
    CARDS = "cards"
    BOOKING_POINTS = "booking_points"
    FREE_KICKS = "free_kicks"
    OFFSIDES = "offsides"
    PENALTIES = "penalties"
    GOALSCORER = "goalscorer"
    PLAYER_GOALS = "player_goals"
    PLAYER_ASSISTS = "player_assists"
    PLAYER_SHOTS = "player_shots"
    PLAYER_SHOTS_ON_TARGET = "player_shots_on_target"
    PLAYER_PASSES = "player_passes"
    PLAYER_TACKLES = "player_tackles"
    PLAYER_CARDS = "player_cards"
    NEXT_GOAL = "next_goal"
    NEXT_GOALSCORER = "next_goalscorer"
    NEXT_SCORING_TYPE = "next_scoring_type"
    REST_OF_MATCH = "rest_of_match"
    TO_QUALIFY = "to_qualify"
    OUTRIGHT = "outright"
    COMBO = "combo"
    SPECIAL = "special"


@dataclass(frozen=True)
class MarketDefinition:
    key: str
    family: MarketFamily
    name: str
    periods: tuple[str, ...] = ("match",)
    player_market: bool = False
    line_based: bool = False
    dynamic: bool = False
    aliases: tuple[str, ...] = ()


MARKET_CATALOG: tuple[MarketDefinition, ...] = (
    MarketDefinition("1x2", MarketFamily.RESULT, "1X2 / Match Result", aliases=("moneyline", "match winner", "winner")),
    MarketDefinition("double_chance", MarketFamily.DOUBLE_CHANCE, "Double Chance"),
    MarketDefinition("draw_no_bet", MarketFamily.DRAW_NO_BET, "Draw No Bet"),
    MarketDefinition("handicap", MarketFamily.HANDICAP, "European Handicap", line_based=True),
    MarketDefinition("asian_handicap", MarketFamily.ASIAN_HANDICAP, "Asian Handicap", line_based=True, aliases=("asian spread",)),
    MarketDefinition("totals", MarketFamily.TOTAL_GOALS, "Total Goals Over/Under", line_based=True, aliases=("over under", "goals o/u")),
    MarketDefinition("team_totals", MarketFamily.TEAM_TOTAL_GOALS, "Team Total Goals", line_based=True),
    MarketDefinition("btts", MarketFamily.BTTS, "Both Teams To Score", aliases=("gg/ng", "gg", "ng")),
    MarketDefinition("correct_score", MarketFamily.CORRECT_SCORE, "Correct Score", dynamic=True),
    MarketDefinition("exact_goals", MarketFamily.EXACT_GOALS, "Exact Match Goals", dynamic=True),
    MarketDefinition("halftime_1x2", MarketFamily.HALF_TIME, "1st Half Result", periods=("1h",)),
    MarketDefinition("halftime_fulltime", MarketFamily.HALF_TIME_FULL_TIME, "Half Time / Full Time", periods=("1h", "match"), dynamic=True),
    MarketDefinition("corners", MarketFamily.CORNERS, "Corners Over/Under", line_based=True),
    MarketDefinition("corners_1x2", MarketFamily.CORNERS, "Corners 1X2"),
    MarketDefinition("team_corners", MarketFamily.CORNERS, "Team Corners", line_based=True),
    MarketDefinition("cards", MarketFamily.CARDS, "Match Cards / Bookings", line_based=True),
    MarketDefinition("booking_points", MarketFamily.BOOKING_POINTS, "Booking Points", line_based=True),
    MarketDefinition("free_kicks", MarketFamily.FREE_KICKS, "Free Kicks", line_based=True),
    MarketDefinition("offsides", MarketFamily.OFFSIDES, "Offsides", line_based=True),
    MarketDefinition("penalties", MarketFamily.PENALTIES, "Penalties", dynamic=True),
    MarketDefinition("goalscorer", MarketFamily.GOALSCORER, "Goalscorer", player_market=True, dynamic=True),
    MarketDefinition("player_goals", MarketFamily.PLAYER_GOALS, "Player Goals", player_market=True, line_based=True),
    MarketDefinition("player_assists", MarketFamily.PLAYER_ASSISTS, "Player Assists", player_market=True, line_based=True),
    MarketDefinition("player_shots", MarketFamily.PLAYER_SHOTS, "Player Shots", player_market=True, line_based=True),
    MarketDefinition("player_shots_on_target", MarketFamily.PLAYER_SHOTS_ON_TARGET, "Player Shots on Target", player_market=True, line_based=True),
    MarketDefinition("player_passes", MarketFamily.PLAYER_PASSES, "Player Passes", player_market=True, line_based=True),
    MarketDefinition("player_tackles", MarketFamily.PLAYER_TACKLES, "Player Tackles", player_market=True, line_based=True),
    MarketDefinition("player_cards", MarketFamily.PLAYER_CARDS, "Player Cards", player_market=True, dynamic=True),
    MarketDefinition("next_goal", MarketFamily.NEXT_GOAL, "Next Goal", dynamic=True),
    MarketDefinition("next_goalscorer", MarketFamily.NEXT_GOALSCORER, "Next Goalscorer", player_market=True, dynamic=True),
    MarketDefinition("next_scoring_type", MarketFamily.NEXT_SCORING_TYPE, "Next Scoring Type", dynamic=True),
    MarketDefinition("rest_of_match", MarketFamily.REST_OF_MATCH, "Rest of Match", dynamic=True),
    MarketDefinition("to_qualify", MarketFamily.TO_QUALIFY, "To Qualify", dynamic=True),
    MarketDefinition("outright", MarketFamily.OUTRIGHT, "Outright / Futures", dynamic=True),
    MarketDefinition("combo", MarketFamily.COMBO, "Combination / Bet Builder", dynamic=True),
    MarketDefinition("special", MarketFamily.SPECIAL, "Special / Novelty", dynamic=True),
)


_PROVIDER_MARKET_KEYS: dict[str, dict[str, str]] = {
    "the-odds-api": {
        "h2h": "1x2", "double_chance": "double_chance", "draw_no_bet": "draw_no_bet",
        "spreads": "asian_handicap", "alternate_spreads": "asian_handicap",
        "totals": "totals", "alternate_totals": "totals",
        "team_totals": "team_totals", "alternate_team_totals": "team_totals",
        "btts": "btts", "correct_score": "correct_score", "correct_score_h1": "correct_score",
        "corners_1x2": "corners_1x2", "alternate_spreads_corners": "corners",
        "alternate_totals_corners": "corners", "alternate_team_totals_corners": "team_corners",
        "alternate_spreads_cards": "cards", "alternate_totals_cards": "cards",
        "halftime_fulltime": "halftime_fulltime", "to_qualify": "to_qualify",
        "player_shots": "player_shots", "player_assists": "player_assists",
    },
    "sportybet": {
        "1": "1x2", "10": "double_chance", "11": "draw_no_bet", "14": "handicap",
        "16": "asian_handicap", "18": "totals", "29": "btts", "45": "correct_score",
        "47": "halftime_fulltime", "60": "halftime_1x2", "219": "1x2",
        "223": "handicap", "225": "totals", "227": "team_totals", "228": "team_totals",
    },
    "sportmonks": {},
    "stake": {},
    "bet365": {},
}


def catalog() -> tuple[MarketDefinition, ...]:
    return MARKET_CATALOG


def normalize_market_key(provider: str, provider_key: str, description: str = "") -> str | None:
    """Return the canonical catalog key for a provider market."""
    provider_keys = _PROVIDER_MARKET_KEYS.get(provider.lower(), {})
    if provider_key in provider_keys:
        return provider_keys[provider_key]
    haystack = f"{provider_key} {description}".lower()
    for market in MARKET_CATALOG:
        if haystack == market.key or any(alias in haystack for alias in market.aliases):
            return market.key
    return None


def provider_market_mapping(provider: str) -> dict[str, str]:
    return dict(_PROVIDER_MARKET_KEYS.get(provider.lower(), {}))

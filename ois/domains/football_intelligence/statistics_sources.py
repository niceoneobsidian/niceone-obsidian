"""Provider-neutral football match and player statistics ingestion.

The adapters normalize API-Football and Sportmonks responses into deterministic
OIS evidence. Network access is injected so credentials, retries, caching and
persistence remain platform-owned concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Callable, Mapping

from pydantic import BaseModel, ConfigDict, Field


JsonTransport = Callable[[str, Mapping[str, str], Mapping[str, str]], Mapping[str, Any]]


class MatchStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str
    team_id: str
    shots_total: float | None = None
    shots_on_target: float | None = None
    shots_off_target: float | None = None
    possession_pct: float | None = Field(default=None, ge=0, le=100)
    corners: float | None = None
    offsides: float | None = None
    fouls: float | None = None
    yellow_cards: float | None = None
    red_cards: float | None = None
    saves: float | None = None
    passes: float | None = None
    accurate_passes: float | None = None
    xg: float | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_id: str
    payload_hash: str


class PlayerMatchStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str
    player_id: str
    player_name: str
    team_id: str
    minutes: float | None = None
    rating: float | None = None
    position: str | None = None
    shots: float | None = None
    shots_on_target: float | None = None
    goals: float | None = None
    assists: float | None = None
    key_passes: float | None = None
    passes: float | None = None
    tackles: float | None = None
    interceptions: float | None = None
    duels_won: float | None = None
    dribbles_successful: float | None = None
    fouls_committed: float | None = None
    fouls_drawn: float | None = None
    yellow_cards: float | None = None
    red_cards: float | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_id: str
    payload_hash: str


class MatchFeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: str
    home_team_id: str
    away_team_id: str
    kickoff_at: datetime | None = None
    status: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    source_id: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload_hash: str
    team_statistics: tuple[MatchStatistics, ...] = ()
    player_statistics: tuple[PlayerMatchStatistics, ...] = ()


def _hash(payload: Any) -> str:
    return sha256(repr(payload).encode("utf-8")).hexdigest()


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.replace("%", "").strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _api_football_stats(raw: Mapping[str, Any], source_id: str) -> tuple[MatchStatistics, ...]:
    response = raw.get("response", [])
    result: list[MatchStatistics] = []
    for block in response if isinstance(response, list) else []:
        team = block.get("team", {})
        values = {
            str(item.get("type", "")).lower().replace(" ", "_"): _num(item.get("value"))
            for item in block.get("statistics", [])
        }
        result.append(
            MatchStatistics(
                match_id=str(raw.get("parameters", {}).get("fixture", "")),
                team_id=str(team.get("id", "")),
                shots_total=values.get("total_shots"),
                shots_on_target=values.get("shots_on_goal"),
                shots_off_target=values.get("shots_off_goal"),
                possession_pct=values.get("ball_possession"),
                corners=values.get("corner_kicks"),
                offsides=values.get("offsides"),
                fouls=values.get("fouls"),
                yellow_cards=values.get("yellow_cards"),
                red_cards=values.get("red_cards"),
                saves=values.get("goalkeeper_saves"),
                passes=values.get("total_passes"),
                accurate_passes=values.get("passes_accurate"),
                observed_at=datetime.now(UTC),
                source_id=source_id,
                payload_hash=_hash(block),
            )
        )
    return tuple(result)


def _api_football_players(raw: Mapping[str, Any], source_id: str) -> tuple[PlayerMatchStatistics, ...]:
    response = raw.get("response", [])
    result: list[PlayerMatchStatistics] = []
    for team_block in response if isinstance(response, list) else []:
        team = team_block.get("team", {})
        for player_block in team_block.get("players", []):
            player = player_block.get("player", {})
            stats = (player_block.get("statistics") or [{}])[0]
            shots = stats.get("shots") or {}
            goals = stats.get("goals") or {}
            passes = stats.get("passes") or {}
            tackles = stats.get("tackles") or {}
            duels = stats.get("duels") or {}
            dribbles = stats.get("dribbles") or {}
            fouls = stats.get("fouls") or {}
            cards = stats.get("cards") or {}
            result.append(
                PlayerMatchStatistics(
                    match_id=str(raw.get("parameters", {}).get("fixture", "")),
                    player_id=str(player.get("id", "")),
                    player_name=str(player.get("name", "")),
                    team_id=str(team.get("id", "")),
                    minutes=_num(stats.get("games", {}).get("minutes")),
                    rating=_num(stats.get("games", {}).get("rating")),
                    position=stats.get("games", {}).get("position"),
                    shots=_num(shots.get("total")),
                    shots_on_target=_num(shots.get("on")),
                    goals=_num(goals.get("total")),
                    assists=_num(goals.get("assists")),
                    key_passes=_num(passes.get("key")),
                    passes=_num(passes.get("total")),
                    tackles=_num(tackles.get("total")),
                    interceptions=_num(tackles.get("interceptions")),
                    duels_won=_num(duels.get("won")),
                    dribbles_successful=_num(dribbles.get("success")),
                    fouls_committed=_num(fouls.get("committed")),
                    fouls_drawn=_num(fouls.get("drawn")),
                    yellow_cards=_num(cards.get("yellow")),
                    red_cards=_num(cards.get("red")),
                    observed_at=datetime.now(UTC),
                    source_id=source_id,
                    payload_hash=_hash(player_block),
                )
            )
    return tuple(result)


def parse_api_football_fixture(raw: Mapping[str, Any], source_id: str = "api-football") -> MatchFeed:
    """Normalize a `/fixtures?id=...` response with embedded match data."""
    response = raw.get("response", [])
    fixture = response[0] if isinstance(response, list) and response else {}
    fixture_info = fixture.get("fixture", {})
    teams = fixture.get("teams", {})
    goals = fixture.get("goals", {})
    return MatchFeed(
        match_id=str(fixture_info.get("id", "")),
        home_team_id=str(teams.get("home", {}).get("id", "")),
        away_team_id=str(teams.get("away", {}).get("id", "")),
        kickoff_at=_parse_dt(fixture_info.get("date")),
        status=fixture_info.get("status", {}).get("short"),
        home_score=goals.get("home"),
        away_score=goals.get("away"),
        source_id=source_id,
        payload_hash=_hash(fixture),
    )


def parse_api_football_statistics(raw: Mapping[str, Any], source_id: str = "api-football") -> tuple[MatchStatistics, ...]:
    return _api_football_stats(raw, source_id)


def parse_api_football_players(raw: Mapping[str, Any], source_id: str = "api-football") -> tuple[PlayerMatchStatistics, ...]:
    return _api_football_players(raw, source_id)


def parse_sportmonks_fixture(raw: Mapping[str, Any], source_id: str = "sportmonks") -> MatchFeed:
    """Normalize a Sportmonks fixture with `stats` and `lineups.details` includes."""
    data = raw.get("data", raw)
    participants = data.get("participants", [])
    home = next((p for p in participants if p.get("meta", {}).get("location") == "home"), {})
    away = next((p for p in participants if p.get("meta", {}).get("location") == "away"), {})
    scores = data.get("scores", [])
    home_score = next((s.get("score", {}).get("goals") for s in scores if s.get("description") == "CURRENT" and s.get("participant_id") == home.get("id")), None)
    away_score = next((s.get("score", {}).get("goals") for s in scores if s.get("description") == "CURRENT" and s.get("participant_id") == away.get("id")), None)
    return MatchFeed(
        match_id=str(data.get("id", "")),
        home_team_id=str(home.get("id", "")),
        away_team_id=str(away.get("id", "")),
        kickoff_at=_parse_dt(data.get("starting_at")),
        status=str(data.get("state", {}).get("developer_name", "")),
        home_score=home_score,
        away_score=away_score,
        source_id=source_id,
        payload_hash=_hash(data),
    )


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

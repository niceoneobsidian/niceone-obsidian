"""Deterministic HTTP clients for supported football data providers.

Credentials are supplied by the caller; no provider secrets are stored in OIS.
The clients normalize only identity/statistics needed by Football Intelligence.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ois.integration.football.models import (
    FootballFixture,
    FootballPlayer,
    PlayerMatchStat,
    PlayerSeasonStat,
)


class FootballProviderError(RuntimeError):
    """Raised when a provider request or response is invalid."""


class _JsonClient:
    def __init__(self, base_url: str, headers: dict[str, str], timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"Accept": "application/json", **headers}
        self.timeout = timeout

    def get(self, path: str, params: dict[str, str | int] | None = None) -> dict[str, Any]:
        query = f"?{urlencode(params)}" if params else ""
        request = Request(f"{self.base_url}/{path.lstrip('/')}{query}", headers=self.headers)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except Exception as exc:
            raise FootballProviderError(f"football provider request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise FootballProviderError("football provider returned a non-object JSON payload")
        return payload


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise FootballProviderError("fixture timestamp is missing or invalid")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class ApiFootballClient:
    """API-Sports/API-Football adapter for fixtures and player statistics."""

    provider = "api-football"

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self._client = _JsonClient(
            "https://v3.football.api-sports.io",
            {"x-apisports-key": api_key},
            timeout,
        )

    def fixtures_by_date(self, day: date) -> list[FootballFixture]:
        payload = self._client.get("fixtures", {"date": day.isoformat()})
        return [self._fixture(item) for item in payload.get("response", [])]

    def fixture(self, fixture_id: str) -> FootballFixture:
        payload = self._client.get("fixtures", {"id": fixture_id})
        response = payload.get("response", [])
        if not response:
            raise FootballProviderError(f"fixture not found: {fixture_id}")
        return self._fixture(response[0])

    def player_season_stats(self, player_id: str, season: int) -> list[PlayerSeasonStat]:
        payload = self._client.get("players", {"id": player_id, "season": season})
        response = payload.get("response", [])
        return [self._player_season_stat(item, str(season)) for item in response]

    def player_match_stats(self, fixture_id: str) -> list[PlayerMatchStat]:
        payload = self._client.get("fixtures/players", {"fixture": fixture_id})
        output: list[PlayerMatchStat] = []
        for team_block in payload.get("response", []):
            team_id = str(team_block.get("team", {}).get("id", ""))
            for block in team_block.get("players", []):
                player_id = str(block.get("player", {}).get("id", ""))
                for metric, value in (block.get("statistics") or [{}])[0].items():
                    if metric == "games":
                        continue
                    output.append(
                        PlayerMatchStat(
                            provider=self.provider,
                            fixture_id=str(fixture_id),
                            player_id=player_id,
                            team_id=team_id or None,
                            metric=metric,
                            value=value,
                        )
                    )
        return output

    def _fixture(self, item: dict[str, Any]) -> FootballFixture:
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        fixture = item.get("fixture", {})
        league = item.get("league", {})
        return FootballFixture(
            provider=self.provider,
            provider_fixture_id=str(fixture.get("id")),
            starting_at=_parse_datetime(fixture.get("date")),
            home_team_id=str(teams.get("home", {}).get("id")),
            home_team_name=str(teams.get("home", {}).get("name", "")),
            away_team_id=str(teams.get("away", {}).get("id")),
            away_team_name=str(teams.get("away", {}).get("name", "")),
            status=(fixture.get("status") or {}).get("short"),
            home_score=_as_int(goals.get("home")),
            away_score=_as_int(goals.get("away")),
            league_id=str(league.get("id")) if league.get("id") is not None else None,
            season_id=str(league.get("season")) if league.get("season") is not None else None,
            raw=item,
        )

    def _player_season_stat(self, item: dict[str, Any], season: str) -> PlayerSeasonStat:
        player = item.get("player", {})
        statistics = item.get("statistics", [])
        stat = statistics[0] if statistics else {}
        games = stat.get("games", {})
        shots = stat.get("shots", {})
        passes = stat.get("passes", {})
        tackles = stat.get("tackles", {})
        return PlayerSeasonStat(
            provider=self.provider,
            player_id=str(player.get("id")),
            season_id=season,
            team_id=str(stat.get("team", {}).get("id")) if stat.get("team") else None,
            appearances=_as_int(games.get("appearences")),
            minutes=_as_int(games.get("minutes")),
            goals=_as_int(stat.get("goals", {}).get("total")),
            assists=_as_int(stat.get("goals", {}).get("assists")),
            shots=_as_int(shots.get("total")),
            shots_on_target=_as_int(shots.get("on")),
            passes=_as_int(passes.get("total")),
            tackles=_as_int(tackles.get("total")),
            interceptions=_as_int(tackles.get("interceptions")),
            cards=_as_int(stat.get("cards", {}).get("yellow")),
            rating=_as_float(games.get("rating")),
            raw=item,
        )


class SportmonksClient:
    """Sportmonks v3 adapter; includes keep match and player data in one request."""

    provider = "sportmonks"

    def __init__(self, api_token: str, timeout: float = 10.0) -> None:
        self._client = _JsonClient(
            "https://api.sportmonks.com/v3/football",
            {"Authorization": api_token},
            timeout,
        )

    def fixtures_by_date(self, day: date) -> list[FootballFixture]:
        payload = self._client.get(f"fixtures/date/{day.isoformat()}")
        return [self._fixture(item) for item in payload.get("data", [])]

    def fixture(self, fixture_id: str) -> FootballFixture:
        payload = self._client.get(
            f"fixtures/{fixture_id}",
            {"include": "participants;scores;events;statistics;lineups.player;lineups.details"},
        )
        return self._fixture(payload.get("data", {}))

    def player(self, player_id: str) -> FootballPlayer:
        payload = self._client.get(
            f"players/{player_id}",
            {"include": "teams;statistics.details.type"},
        )
        item = payload.get("data", {})
        return FootballPlayer(
            provider=self.provider,
            provider_player_id=str(item.get("id")),
            name=str(item.get("display_name") or item.get("name") or ""),
            team_id=self._first_team_id(item),
            position=str(item.get("position_id")) if item.get("position_id") else None,
            raw=item,
        )

    def player_match_stats(self, fixture_id: str) -> list[PlayerMatchStat]:
        fixture = self.fixture(fixture_id)
        output: list[PlayerMatchStat] = []
        for lineup in fixture.raw.get("lineups", []):
            player = lineup.get("player") or {}
            player_id = str(player.get("id", lineup.get("player_id", "")))
            team_id = str(lineup.get("team_id")) if lineup.get("team_id") else None
            for detail in lineup.get("details", []):
                metric = str((detail.get("type") or {}).get("name") or detail.get("type_id"))
                value = (detail.get("data") or {}).get("value")
                output.append(
                    PlayerMatchStat(
                        provider=self.provider,
                        fixture_id=str(fixture_id),
                        player_id=player_id,
                        team_id=team_id,
                        metric=metric,
                        value=value,
                    )
                )
        return output

    def player_season_stats(self, player_id: str, season_id: str) -> list[PlayerSeasonStat]:
        payload = self._client.get(
            f"players/{player_id}",
            {"include": "statistics.details.type;statistics.team", "filters": f"playerStatisticSeasons:{season_id}"},
        )
        item = payload.get("data", {})
        output: list[PlayerSeasonStat] = []
        for stat in item.get("statistics", []):
            details = {str(d.get("type_id")): (d.get("data") or {}).get("value") for d in stat.get("details", [])}
            output.append(
                PlayerSeasonStat(
                    provider=self.provider,
                    player_id=str(player_id),
                    season_id=str(season_id),
                    team_id=str(stat.get("team_id")) if stat.get("team_id") else None,
                    appearances=_as_int(details.get("appearances")),
                    minutes=_as_int(details.get("minutes_played")),
                    goals=_as_int(details.get("goals")),
                    assists=_as_int(details.get("assists")),
                    shots=_as_int(details.get("shots")),
                    shots_on_target=_as_int(details.get("shots_on_target")),
                    passes=_as_int(details.get("passes")),
                    tackles=_as_int(details.get("tackles")),
                    interceptions=_as_int(details.get("interceptions")),
                    cards=_as_int(details.get("yellowcards")),
                    rating=_as_float(details.get("rating")),
                    raw=stat,
                )
            )
        return output

    def _fixture(self, item: dict[str, Any]) -> FootballFixture:
        participants = item.get("participants", [])
        home = next((p for p in participants if p.get("meta", {}).get("location") == "home"), {})
        away = next((p for p in participants if p.get("meta", {}).get("location") == "away"), {})
        scores = item.get("scores", [])
        current = next((s for s in scores if s.get("description") == "CURRENT"), {})
        score = current.get("score") or {}
        return FootballFixture(
            provider=self.provider,
            provider_fixture_id=str(item.get("id")),
            starting_at=_parse_datetime(item.get("starting_at")),
            home_team_id=str(home.get("id")),
            home_team_name=str(home.get("name", "")),
            away_team_id=str(away.get("id")),
            away_team_name=str(away.get("name", "")),
            status=(item.get("state") or {}).get("short_name"),
            home_score=_as_int(score.get("goals")) if score.get("participant") == "home" else None,
            away_score=None,
            league_id=str(item.get("league_id")) if item.get("league_id") else None,
            season_id=str(item.get("season_id")) if item.get("season_id") else None,
            raw=item,
        )

    @staticmethod
    def _first_team_id(item: dict[str, Any]) -> str | None:
        teams = item.get("teams", [])
        if teams and isinstance(teams[0], dict) and teams[0].get("team_id"):
            return str(teams[0]["team_id"])
        return None

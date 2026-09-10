"""Small provider clients for football statistics.

Credentials are read from the environment by callers and never persisted in OIS
state. The HTTP transport is injectable for deterministic tests and governed
runtime execution.
"""

from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any, Mapping

from .statistics_sources import MatchFeed, MatchStatistics, PlayerMatchStatistics, parse_api_football_fixture, parse_api_football_players, parse_api_football_statistics


class StatisticsClientError(RuntimeError):
    """Raised when a provider request cannot be completed or parsed."""


def urllib_json_transport(url: str, headers: Mapping[str, str], params: Mapping[str, str]) -> Mapping[str, Any]:
    query = urlencode(params)
    target = f"{url}?{query}" if query else url
    request = Request(target, headers=dict(headers), method="GET")
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - explicit HTTPS allowlist below
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - network failures belong to integration tests
        raise StatisticsClientError(f"football provider request failed: {type(exc).__name__}") from exc


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise StatisticsClientError(f"missing required environment variable: {name}")
    return value


def api_football_fixture(
    fixture_id: str,
    *,
    transport=urllib_json_transport,
) -> MatchFeed:
    """Fetch one API-Football fixture.

    API-Football documents `/fixtures?id=...` and embedded events, lineups,
    statistics and players. The caller may separately request statistics and
    player-performance endpoints when deeper data is required.
    """
    raw = transport(
        "https://v3.football.api-sports.io/fixtures",
        {"x-apisports-key": _required_env("API_FOOTBALL_KEY")},
        {"id": fixture_id},
    )
    return parse_api_football_fixture(raw)


def api_football_match_statistics(
    fixture_id: str,
    *,
    transport=urllib_json_transport,
) -> tuple[MatchStatistics, ...]:
    raw = transport(
        "https://v3.football.api-sports.io/fixtures/statistics",
        {"x-apisports-key": _required_env("API_FOOTBALL_KEY")},
        {"fixture": fixture_id},
    )
    return parse_api_football_statistics(raw)


def api_football_player_statistics(
    fixture_id: str,
    *,
    transport=urllib_json_transport,
) -> tuple[PlayerMatchStatistics, ...]:
    raw = transport(
        "https://v3.football.api-sports.io/fixtures/players",
        {"x-apisports-key": _required_env("API_FOOTBALL_KEY")},
        {"fixture": fixture_id},
    )
    return parse_api_football_players(raw)


def sportmonks_fixture(
    fixture_id: str,
    *,
    transport=urllib_json_transport,
) -> MatchFeed:
    """Fetch a Sportmonks fixture with lineup/player detail context."""
    raw = transport(
        f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}",
        {},
        {
            "api_token": _required_env("SPORTMONKS_API_TOKEN"),
            "include": "stats;lineups.details",
        },
    )
    return _sportmonks_fixture(raw)


def _sportmonks_fixture(raw: Mapping[str, Any]) -> MatchFeed:
    from .statistics_sources import parse_sportmonks_fixture

    return parse_sportmonks_fixture(raw)

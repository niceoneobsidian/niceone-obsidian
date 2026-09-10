"""Provider-neutral football data-feed contracts and HTTP transport.

The domain owns normalization and evidence contracts; credentials, network policy,
rate limits and persistence remain platform concerns.
"""

from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from .schemas import FootballEvidence


class FeedError(RuntimeError):
    """Raised when a provider feed cannot produce a valid response."""


class FeedConfigurationError(FeedError):
    """Raised when provider credentials/configuration are missing."""


class FeedResponseError(FeedError):
    """Raised when a provider returns an invalid or unsuccessful response."""


class FeedObservation(BaseModel):
    """Raw provider observation retained as auditable evidence."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    resource: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload_sha256: str
    payload: dict[str, Any]

    @property
    def evidence(self) -> FootballEvidence:
        return FootballEvidence(
            source_id=f"{self.provider}:{self.resource}:{self.payload_sha256[:16]}",
            uri=self.resource,
            observed_at=self.observed_at,
            confidence=1.0,
        )


class MatchFeed(BaseModel):
    """Canonical match state independent of provider schema."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    provider_match_id: str
    competition: str
    kickoff_at: datetime | None = None
    status: str
    minute: int | None = None
    home_team_id: str
    home_team: str
    away_team_id: str
    away_team: str
    home_score: int | None = None
    away_score: int | None = None
    evidence: list[FootballEvidence] = Field(default_factory=list)


class TeamStatFeed(BaseModel):
    """Canonical team statistics for one match."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    provider_match_id: str
    team_id: str
    team_name: str
    statistics: dict[str, float | int | str | None] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence: list[FootballEvidence] = Field(default_factory=list)


class PlayerStatFeed(BaseModel):
    """Canonical player statistics for one match."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    provider_match_id: str
    player_id: str
    player_name: str
    team_id: str
    minutes: int | None = None
    position: str | None = None
    rating: float | None = None
    statistics: dict[str, float | int | str | None] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence: list[FootballEvidence] = Field(default_factory=list)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    payload: dict[str, Any]


Transport = Callable[[str, dict[str, str], dict[str, str]], HttpResponse]


def default_transport(url: str, headers: dict[str, str], params: dict[str, str]) -> HttpResponse:
    """Small dependency-free JSON transport with an explicit timeout."""
    query = urlencode(params)
    target = f"{url}?{query}" if query else url
    request = Request(target, headers={"Accept": "application/json", **headers})
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise FeedResponseError("Provider response must be a JSON object")
            return HttpResponse(status=response.status, payload=payload)
    except HTTPError as exc:
        raise FeedResponseError(f"Provider returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise FeedResponseError(f"Provider request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise FeedResponseError("Provider returned invalid JSON") from exc


def payload_hash(payload: dict[str, Any]) -> str:
    """Create a deterministic hash for provenance/audit records."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class FootballFeedProvider(ABC):
    """Interface implemented by each football statistics provider."""

    provider_name: str

    @abstractmethod
    def live_matches(self) -> tuple[MatchFeed, ...]:
        """Return currently live matches."""

    @abstractmethod
    def match_statistics(self, match_id: str) -> tuple[TeamStatFeed, ...]:
        """Return team statistics for a match."""

    @abstractmethod
    def player_statistics(self, match_id: str) -> tuple[PlayerStatFeed, ...]:
        """Return player statistics for a match."""


class APIFootballProvider(FootballFeedProvider):
    """API-Football v3 adapter.

    Endpoint contract: /fixtures, /fixtures/statistics and /fixtures/players.
    The key is read from API_FOOTBALL_KEY and is never stored in the domain.
    """

    provider_name = "api-football"
    base_url = "https://v3.football.api-sports.io"

    def __init__(self, api_key: str | None = None, transport: Transport = default_transport) -> None:
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY")
        if not self.api_key:
            raise FeedConfigurationError("API_FOOTBALL_KEY is not configured")
        self.transport = transport

    def _get(self, resource: str, params: dict[str, str]) -> FeedObservation:
        response = self.transport(
            f"{self.base_url}{resource}",
            {"x-apisports-key": self.api_key or ""},
            params,
        )
        if response.status < 200 or response.status >= 300:
            raise FeedResponseError(f"API-Football HTTP status {response.status}")
        if response.payload.get("errors"):
            raise FeedResponseError(f"API-Football errors: {response.payload['errors']}")
        return FeedObservation(
            provider=self.provider_name,
            resource=f"{self.base_url}{resource}",
            payload_sha256=payload_hash(response.payload),
            payload=response.payload,
        )

    def live_matches(self) -> tuple[MatchFeed, ...]:
        observation = self._get("/fixtures", {"live": "all"})
        return tuple(self._match(item, observation.evidence) for item in observation.payload.get("response", []))

    def match_statistics(self, match_id: str) -> tuple[TeamStatFeed, ...]:
        observation = self._get("/fixtures/statistics", {"fixture": match_id})
        rows: list[TeamStatFeed] = []
        for item in observation.payload.get("response", []):
            team = item.get("team") or {}
            stats = {str(row.get("type")): row.get("value") for row in item.get("statistics", [])}
            rows.append(
                TeamStatFeed(
                    provider=self.provider_name,
                    provider_match_id=match_id,
                    team_id=str(team.get("id", "")),
                    team_name=str(team.get("name", "")),
                    statistics=stats,
                    evidence=[observation.evidence],
                )
            )
        return tuple(rows)

    def player_statistics(self, match_id: str) -> tuple[PlayerStatFeed, ...]:
        observation = self._get("/fixtures/players", {"fixture": match_id})
        rows: list[PlayerStatFeed] = []
        for team_block in observation.payload.get("response", []):
            team = team_block.get("team") or {}
            for player_block in team_block.get("players", []):
                player = player_block.get("player") or {}
                statistics = (player_block.get("statistics") or [{}])[0]
                games = statistics.get("games") or {}
                rows.append(
                    PlayerStatFeed(
                        provider=self.provider_name,
                        provider_match_id=match_id,
                        player_id=str(player.get("id", "")),
                        player_name=str(player.get("name", "")),
                        team_id=str(team.get("id", "")),
                        minutes=games.get("minutes"),
                        position=games.get("position"),
                        rating=_float_or_none(games.get("rating")),
                        statistics=_flatten_statistics(statistics),
                        evidence=[observation.evidence],
                    )
                )
        return tuple(rows)

    def _match(self, item: dict[str, Any], evidence: FootballEvidence) -> MatchFeed:
        fixture = item.get("fixture") or {}
        teams = item.get("teams") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        goals = item.get("goals") or {}
        status = fixture.get("status") or {}
        kickoff = fixture.get("date")
        return MatchFeed(
            provider=self.provider_name,
            provider_match_id=str(fixture.get("id", "")),
            competition=str((item.get("league") or {}).get("name", "")),
            kickoff_at=datetime.fromisoformat(kickoff.replace("Z", "+00:00")) if kickoff else None,
            status=str(status.get("short", "")),
            minute=status.get("elapsed"),
            home_team_id=str(home.get("id", "")),
            home_team=str(home.get("name", "")),
            away_team_id=str(away.get("id", "")),
            away_team=str(away.get("name", "")),
            home_score=goals.get("home"),
            away_score=goals.get("away"),
            evidence=[evidence],
        )


class SportmonksProvider(FootballFeedProvider):
    """Sportmonks v3 adapter using fixture includes to avoid N+1 calls."""

    provider_name = "sportmonks"
    base_url = "https://api.sportmonks.com/v3/football"

    def __init__(self, token: str | None = None, transport: Transport = default_transport) -> None:
        self.token = token or os.getenv("SPORTMONKS_API_TOKEN")
        if not self.token:
            raise FeedConfigurationError("SPORTMONKS_API_TOKEN is not configured")
        self.transport = transport

    def _get(self, resource: str, params: dict[str, str] | None = None) -> FeedObservation:
        query = {"api_token": self.token or "", **(params or {})}
        response = self.transport(f"{self.base_url}{resource}", {}, query)
        if response.status < 200 or response.status >= 300:
            raise FeedResponseError(f"Sportmonks HTTP status {response.status}")
        return FeedObservation(
            provider=self.provider_name,
            resource=f"{self.base_url}{resource}",
            payload_sha256=payload_hash(response.payload),
            payload=response.payload,
        )

    def live_matches(self) -> tuple[MatchFeed, ...]:
        observation = self._get("/livescores/latest", {"include": "participants;scores"})
        return tuple(self._match(item, observation.evidence) for item in observation.payload.get("data", []))

    def match_statistics(self, match_id: str) -> tuple[TeamStatFeed, ...]:
        observation = self._get(
            f"/fixtures/{match_id}",
            {"include": "statistics.type;participants"},
        )
        fixture = observation.payload.get("data") or {}
        participants = {str(p.get("id")): p for p in fixture.get("participants", [])}
        rows: list[TeamStatFeed] = []
        for block in fixture.get("statistics", []):
            participant_id = str(block.get("participant_id", ""))
            team = participants.get(participant_id) or {}
            rows.append(
                TeamStatFeed(
                    provider=self.provider_name,
                    provider_match_id=match_id,
                    team_id=participant_id,
                    team_name=str(team.get("name", "")),
                    statistics={str(block.get("type_id", block.get("type", ""))): block.get("data")},
                    evidence=[observation.evidence],
                )
            )
        return tuple(rows)

    def player_statistics(self, match_id: str) -> tuple[PlayerStatFeed, ...]:
        observation = self._get(
            f"/fixtures/{match_id}",
            {"include": "lineups.player;lineups.details.type"},
        )
        fixture = observation.payload.get("data") or {}
        rows: list[PlayerStatFeed] = []
        for lineup in fixture.get("lineups", []):
            player = lineup.get("player") or {}
            details = {
                str(detail.get("type_id", detail.get("type", ""))): detail.get("data")
                for detail in lineup.get("details", [])
            }
            rows.append(
                PlayerStatFeed(
                    provider=self.provider_name,
                    provider_match_id=match_id,
                    player_id=str(player.get("id", lineup.get("player_id", ""))),
                    player_name=str(player.get("name", "")),
                    team_id=str(lineup.get("team_id", "")),
                    minutes=lineup.get("minutes"),
                    position=str(lineup.get("position", "")) or None,
                    rating=_float_or_none(lineup.get("rating")),
                    statistics=details,
                    evidence=[observation.evidence],
                )
            )
        return tuple(rows)

    def _match(self, item: dict[str, Any], evidence: FootballEvidence) -> MatchFeed:
        participants = item.get("participants") or []
        home = next((p for p in participants if p.get("meta", {}).get("location") == "home"), {})
        away = next((p for p in participants if p.get("meta", {}).get("location") == "away"), {})
        scores = item.get("scores") or {}
        return MatchFeed(
            provider=self.provider_name,
            provider_match_id=str(item.get("id", "")),
            competition=str((item.get("league") or {}).get("name", "")),
            kickoff_at=_parse_datetime(item.get("starting_at")),
            status=str(item.get("state", {}).get("short_name", item.get("state_id", ""))),
            minute=None,
            home_team_id=str(home.get("id", "")),
            home_team=str(home.get("name", "")),
            away_team_id=str(away.get("id", "")),
            away_team=str(away.get("name", "")),
            home_score=_score_value(scores, "home"),
            away_score=_score_value(scores, "away"),
            evidence=[evidence],
        )


def _flatten_statistics(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        return {prefix.rstrip("."): value}
    result: dict[str, Any] = {}
    for key, child in value.items():
        result.update(_flatten_statistics(child, f"{prefix}{key}."))
    return result


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _score_value(scores: dict[str, Any], location: str) -> int | None:
    for score in scores.values():
        if isinstance(score, dict) and score.get("description") in {"CURRENT", "current"}:
            participant = score.get("participant")
            if participant == location:
                try:
                    return int(score.get("goals"))
                except (TypeError, ValueError):
                    return None
    return None

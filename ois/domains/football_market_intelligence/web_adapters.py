"""Deterministic parsers for supported football web data providers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from .web_sources import (
    MatchObservation,
    OddsObservation,
    WebObservation,
    WebSource,
    WebTransport,
    implied_probability,
    payload_hash,
)


FOOTBALL_DATA = WebSource(
    source_id="football-data.org",
    provider="football-data.org",
    kind="fixture",
    base_uri="https://api.football-data.org/v4",
    historical=True,
)
ODDS_API = WebSource(
    source_id="the-odds-api",
    provider="The Odds API",
    kind="odds",
    base_uri="https://api.the-odds-api.com/v4",
    historical=True,
)
SPORTMONKS = WebSource(
    source_id="sportmonks",
    provider="Sportmonks",
    kind="odds",
    base_uri="https://api.sportmonks.com/v3/football",
    historical=True,
)


def _dt(value: str | None) -> datetime | None:
    if not value or value in {"None", "null"}:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _id(source_id: str, external_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{source_id}:{external_id}"))


def _obs_base(
    source: WebSource,
    external_id: str,
    observed_at: datetime,
    payload: dict[str, Any],
    uri: str,
) -> dict[str, Any]:
    return {
        "observation_id": _id(source.source_id, external_id),
        "source_id": source.source_id,
        "external_id": external_id,
        "observed_at": observed_at,
        "source_timestamp": None,
        "source_uri": uri,
        "payload_hash": payload_hash(payload),
    }


def parse_football_data_matches(
    payload: dict[str, Any], *, source_uri: str, observed_at: datetime
) -> list[MatchObservation]:
    """Normalize football-data.org v4 match-list or single-match payloads."""
    raw_matches = payload.get("matches")
    matches = raw_matches if isinstance(raw_matches, list) else [payload]
    result: list[MatchObservation] = []
    for raw in matches:
        if not isinstance(raw, dict) or "id" not in raw or "homeTeam" not in raw or "awayTeam" not in raw:
            continue
        home = raw["homeTeam"]
        away = raw["awayTeam"]
        score = raw.get("score") or {}
        full_time = score.get("fullTime") or {}
        base = _obs_base(FOOTBALL_DATA, str(raw["id"]), observed_at, raw, source_uri)
        result.append(
            MatchObservation(
                **base,
                competition=(raw.get("competition") or {}).get("code") or (raw.get("competition") or {}).get("name"),
                kickoff_at=_dt(raw.get("utcDate")) or observed_at,
                status=str(raw.get("status", "UNKNOWN")),
                home_team_id=str(home.get("id", "")),
                home_team_name=str(home.get("name", "")),
                away_team_id=str(away.get("id", "")),
                away_team_name=str(away.get("name", "")),
                home_score=full_time.get("home"),
                away_score=full_time.get("away"),
            )
        )
    return result


def parse_odds_api(payload: dict[str, Any], *, source_uri: str, observed_at: datetime) -> list[OddsObservation]:
    """Normalize The Odds API current or historical snapshot shape."""
    data = payload.get("data")
    if isinstance(data, list):
        events: list[Any] = data
    elif isinstance(data, dict) and isinstance(data.get("data"), list):
        events = data["data"]
    else:
        events = [payload]

    result: list[OddsObservation] = []
    for event in events:
        if not isinstance(event, dict) or "id" not in event:
            continue
        match_id = str(event["id"])
        for bookmaker in event.get("bookmakers", []):
            if not isinstance(bookmaker, dict):
                continue
            bookmaker_name = str(bookmaker.get("title") or bookmaker.get("key") or "unknown")
            for market in bookmaker.get("markets", []):
                if not isinstance(market, dict):
                    continue
                market_type = str(market.get("key", "unknown"))
                for outcome in market.get("outcomes", []):
                    if not isinstance(outcome, dict) or "price" not in outcome:
                        continue
                    price = float(outcome["price"])
                    external_id = (
                        f"{match_id}:{bookmaker_name}:{market_type}:"
                        f"{outcome.get('name')}:{outcome.get('point')}"
                    )
                    result.append(
                        OddsObservation(
                            **_obs_base(ODDS_API, external_id, observed_at, outcome, source_uri),
                            provider=ODDS_API.provider,
                            match_id=match_id,
                            bookmaker=bookmaker_name,
                            market_type=market_type,
                            selection=str(outcome.get("name", "")),
                            line=float(outcome["point"]) if outcome.get("point") is not None else None,
                            decimal_odds=price,
                            implied_probability=implied_probability(price),
                        )
                    )
    return result


def parse_sportmonks_odds(
    payload: dict[str, Any], *, source_uri: str, observed_at: datetime
) -> list[OddsObservation]:
    """Normalize Sportmonks standard/premium odds entries."""
    raw_odds = payload.get("data", [])
    if isinstance(raw_odds, dict):
        raw_odds = raw_odds.get("data", [])
    result: list[OddsObservation] = []
    for raw in raw_odds:
        if not isinstance(raw, dict) or raw.get("value") is None:
            continue
        price = float(raw["value"])
        match_id = str(raw.get("fixture_id", ""))
        bookmaker = str(raw.get("bookmaker_id", "unknown"))
        market = str(raw.get("market_id") or raw.get("market_description") or "unknown")
        selection = str(raw.get("label") or raw.get("name") or "")
        external_id = f"{raw.get('id', '')}:{match_id}:{bookmaker}:{market}:{selection}"
        source_timestamp = _dt(raw.get("latest_bookmaker_update")) or _dt(raw.get("last_update"))
        base = _obs_base(SPORTMONKS, external_id, observed_at, raw, source_uri)
        base["source_timestamp"] = source_timestamp
        result.append(
            OddsObservation(
                **base,
                provider=SPORTMONKS.provider,
                match_id=match_id,
                bookmaker=bookmaker,
                market_type=market,
                selection=selection,
                line=float(raw["line"]) if raw.get("line") is not None else None,
                decimal_odds=price,
                implied_probability=implied_probability(price),
            )
        )
    return result


def fetch_and_parse(
    source: WebSource,
    uri: str,
    transport: WebTransport,
    *,
    headers: dict[str, str] | None = None,
    observed_at: datetime | None = None,
) -> list[WebObservation]:
    """Fetch through an injected transport and dispatch to the provider parser."""
    timestamp = observed_at or datetime.now(UTC)
    payload = transport(uri, headers or {})
    if source.source_id == FOOTBALL_DATA.source_id:
        return parse_football_data_matches(payload, source_uri=uri, observed_at=timestamp)
    if source.source_id == ODDS_API.source_id:
        return parse_odds_api(payload, source_uri=uri, observed_at=timestamp)
    if source.source_id == SPORTMONKS.source_id:
        return parse_sportmonks_odds(payload, source_uri=uri, observed_at=timestamp)
    raise ValueError(f"unsupported web source: {source.source_id}")

"""F1 live/historical provider adapters with canonical normalization.

Network access is optional at import time. The adapter uses Sportmonks v3 when
SPORTMONKS_TOKEN is configured. Source timestamps and raw payload hashes are kept
at the boundary so downstream OIS evidence can prove provenance.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from urllib.request import Request, urlopen
import json

from .origin import FixtureRecord


class SportmonksProvider:
    provider_id = "sportmonks.v3"
    base_url = "https://api.sportmonks.com/v3/football"

    def __init__(self, token: str | None = None, timeout: float = 15.0) -> None:
        self.token = token or os.getenv("SPORTMONKS_TOKEN")
        self.timeout = timeout
        if not self.token:
            raise ValueError("SPORTMONKS_TOKEN is required for live ingestion")

    def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        query = dict(params or {})
        query["api_token"] = self.token or ""
        url = f"{self.base_url}/{path.lstrip('/')}?" + "&".join(f"{k}={v}" for k, v in query.items())
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "OIS-Football/1.0"})
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _dt(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)

    def _normalize(self, row: dict[str, Any]) -> FixtureRecord:
        participants = row.get("participants") or []
        home = next((p for p in participants if p.get("meta", {}).get("location") == "home"), participants[0] if participants else {})
        away = next((p for p in participants if p.get("meta", {}).get("location") == "away"), participants[1] if len(participants) > 1 else {})
        scores = row.get("scores") or []
        home_score = next((s for s in scores if s.get("description") in {"CURRENT", "FT"} and s.get("score", {}).get("participant") == "home"), None)
        away_score = next((s for s in scores if s.get("description") in {"CURRENT", "FT"} and s.get("score", {}).get("participant") == "away"), None)
        xg = row.get("xgfixture") or []
        hxg = next((float(x.get("data", {}).get("value")) for x in xg if x.get("location") == "home" and x.get("type", {}).get("code") == "expected-goals"), None)
        axg = next((float(x.get("data", {}).get("value")) for x in xg if x.get("location") == "away" and x.get("type", {}).get("code") == "expected-goals"), None)
        raw = json.dumps(row, sort_keys=True, default=str).encode()
        source_id = f"{self.provider_id}:{sha256(raw).hexdigest()[:16]}"
        state = (row.get("state") or {}).get("state", "scheduled")
        return FixtureRecord(
            fixture_id=str(row["id"]),
            competition=str((row.get("league") or {}).get("name", row.get("league_id", "unknown"))),
            kickoff_at=self._dt(str(row["starting_at"])),
            home_team_id=str(home.get("id", home.get("team_id", "unknown"))),
            home_team=str(home.get("name", "unknown")),
            away_team_id=str(away.get("id", away.get("team_id", "unknown"))),
            away_team=str(away.get("name", "unknown")),
            home_goals=(home_score or {}).get("score", {}).get("goals") if home_score else None,
            away_goals=(away_score or {}).get("score", {}).get("goals") if away_score else None,
            home_xg=hxg,
            away_xg=axg,
            status=str(state).lower(),
            source_id=source_id,
            observed_at=datetime.now(UTC),
        )

    def fixtures(self, start: datetime, end: datetime) -> list[FixtureRecord]:
        path = f"fixtures/between/{start.date().isoformat()}/{end.date().isoformat()}"
        payload = self._get(path, {"include": "participants;scores;state;xGFixture"})
        return [self._normalize(row) for row in payload.get("data", [])]

    def live(self) -> list[FixtureRecord]:
        payload = self._get("livescores/inplay", {"include": "participants;scores;state;xGFixture;events"})
        return [self._normalize(row) for row in payload.get("data", [])]

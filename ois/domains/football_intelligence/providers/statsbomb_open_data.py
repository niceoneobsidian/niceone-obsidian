"""StatsBomb Open Data adapter for leakage-safe Football replay.

The adapter reads the public JSON repository directly, normalizes one historical
match, and derives only pre-match features from matches earlier than kickoff.
No post-match event data is used to construct the prediction state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.request import Request, urlopen

from ..schemas import FootballEvidence, MatchState, TeamSnapshot

DEFAULT_BASE_URL = "https://raw.githubusercontent.com/hudl/open-data/master/data"


@dataclass(frozen=True)
class StatsBombReplayInput:
    match: MatchState
    actual_outcome: str
    source_id: str
    source_uri: str
    raw_match: dict[str, Any]


class StatsBombOpenDataProvider:
    """Load historical matches from StatsBomb Open Data."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        fetch_json: Callable[[str], Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._fetch_json = fetch_json or self._fetch

    @staticmethod
    def _fetch(url: str) -> Any:
        request = Request(url, headers={"User-Agent": "niceone-obsidian/football-runtime"})
        with urlopen(request, timeout=20) as response:  # noqa: S310 - URL is provider-configured.
            return json.load(response)

    def _matches_url(self, competition_id: int, season_id: int) -> str:
        return f"{self.base_url}/matches/{competition_id}/{season_id}.json"

    def load_matches(self, competition_id: int, season_id: int) -> list[dict[str, Any]]:
        payload = self._fetch_json(self._matches_url(competition_id, season_id))
        if not isinstance(payload, list):
            raise ValueError("StatsBomb matches payload must be a JSON array")
        return [item for item in payload if isinstance(item, dict)]

    @staticmethod
    def _kickoff(record: dict[str, Any]) -> datetime:
        date = record["match_date"]
        time = record.get("kick_off", "00:00:00").split(".", 1)[0]
        return datetime.fromisoformat(f"{date}T{time}").replace(tzinfo=UTC)

    @staticmethod
    def _team(record: dict[str, Any], side: str) -> tuple[str, str]:
        prefix = "home" if side == "home" else "away"
        return str(record[f"{prefix}_team"][f"{prefix}_team_id"]), str(
            record[f"{prefix}_team"][f"{prefix}_team_name"]
        )

    @staticmethod
    def _outcome(record: dict[str, Any]) -> str:
        home_score = int(record["home_score"])
        away_score = int(record["away_score"])
        if home_score > away_score:
            return "home"
        if away_score > home_score:
            return "away"
        return "draw"

    def _snapshot(
        self,
        team_id: str,
        team_name: str,
        historical: list[dict[str, Any]],
        *,
        is_home: bool,
    ) -> TeamSnapshot:
        prior = []
        for record in historical:
            home_id, _ = self._team(record, "home")
            away_id, _ = self._team(record, "away")
            if team_id in (home_id, away_id):
                prior.append(record)
        prior = sorted(prior, key=self._kickoff)[-5:]

        wins = draws = points = goals_for = goals_against = 0
        for record in prior:
            home_score = int(record["home_score"])
            away_score = int(record["away_score"])
            home_id, _ = self._team(record, "home")
            if team_id == home_id:
                gf, ga = home_score, away_score
            else:
                gf, ga = away_score, home_score
            goals_for += gf
            goals_against += ga
            if gf > ga:
                wins += 1
                points += 3
            elif gf == ga:
                draws += 1
                points += 1

        games = len(prior)
        points_per_game = points / games if games else 1.0
        attack = (goals_for / games) / 1.4 if games else 1.0
        defense = 1.4 / max(goals_against / games, 0.25) if games else 1.0
        elo = 1500.0 + (points_per_game - 1.5) * 100.0
        return TeamSnapshot(
            team_id=team_id,
            name=team_name,
            elo=elo,
            attack_strength=max(0.5, min(1.8, attack)),
            defense_strength=max(0.5, min(1.8, defense)),
            home_advantage=0.05 if is_home else 0.0,
            recent_form=(wins + draws * 0.5) / games if games else 0.5,
            rest_days=7.0,
            squad_strength=1.0,
            lineup_confidence=0.5,
        )

    def load_replay(self, competition_id: int, season_id: int, match_id: int) -> StatsBombReplayInput:
        matches = self.load_matches(competition_id, season_id)
        target = next((m for m in matches if int(m.get("match_id", -1)) == match_id), None)
        if target is None:
            raise KeyError(f"StatsBomb match {match_id} not found")

        kickoff = self._kickoff(target)
        historical = [m for m in matches if self._kickoff(m) < kickoff]
        home_id, home_name = self._team(target, "home")
        away_id, away_name = self._team(target, "away")
        competition = str(target["competition"]["competition_name"])
        source_uri = self._matches_url(competition_id, season_id)
        source_id = f"statsbomb.open-data:{competition_id}:{season_id}:{match_id}"

        match = MatchState(
            match_id=str(match_id),
            competition=competition,
            kickoff_at=kickoff,
            home=self._snapshot(home_id, home_name, historical, is_home=True),
            away=self._snapshot(away_id, away_name, historical, is_home=False),
            evidence=[
                FootballEvidence(
                    source_id=source_id,
                    uri=source_uri,
                    observed_at=kickoff,
                    confidence=1.0,
                )
            ],
        )
        return StatsBombReplayInput(
            match=match,
            actual_outcome=self._outcome(target),
            source_id=source_id,
            source_uri=source_uri,
            raw_match=target,
        )

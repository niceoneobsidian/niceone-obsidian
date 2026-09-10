"""Historical StatsBomb corpus builder with strict chronological feature state."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
from statistics import mean
from typing import Any, Iterable, Sequence

from ois.domains.football_intelligence.statsbomb import StatsBombOpenDataProvider

from .models import MatchFeatures
from .pipeline import FeatureSnapshot
from .training import TrainingRow


class HistoricalCorpusBuilder:
    """Convert StatsBomb match/event archives into pre-match training rows.

    Features for match N are computed only from matches preceding N. The current
    match's events are used only to create labels and update the team/player state
    after the row has been emitted.
    """

    def __init__(self, provider: StatsBombOpenDataProvider | None = None, window: int = 8) -> None:
        self.provider = provider or StatsBombOpenDataProvider()
        self.window = max(1, window)

    def build(self, matches: Sequence[dict[str, Any]]) -> tuple[TrainingRow, ...]:
        ordered = sorted(matches, key=lambda match: _parse_datetime(match.get("match_date")))
        team_state: dict[str, deque[tuple[float, float, float, float]]] = defaultdict(lambda: deque(maxlen=self.window))
        rows: list[TrainingRow] = []
        for rank, match in enumerate(ordered):
            home = _team(match, "home")
            away = _team(match, "away")
            home_id, away_id = str(home["id"]), str(away["id"])
            home_prior = _team_rates(team_state[home_id])
            away_prior = _team_rates(team_state[away_id])
            events = self.provider.events(int(match["match_id"]))
            event_rows = events.payload if isinstance(events.payload, list) else []
            labels = _event_labels(event_rows, home.get("team_name", ""), away.get("team_name", ""))
            features = MatchFeatures(
                home_attack=max(0.05, home_prior[0]),
                home_defense=max(0.05, home_prior[1]),
                away_attack=max(0.05, away_prior[0]),
                away_defense=max(0.05, away_prior[1]),
                expected_corners=max(0.1, home_prior[2] + away_prior[2]),
                expected_cards=max(0.1, home_prior[3] + away_prior[3]),
                player_shot_rate=max(0.01, labels["player_shots_rate"]),
                player_sot_rate=max(0.01, labels["player_sot_rate"]),
                player_goal_rate=max(0.0, labels["player_goal_rate"]),
            )
            rows.append(
                TrainingRow(
                    match_id=str(match["match_id"]),
                    as_of_rank=rank,
                    features=features,
                    home_goals=labels["home_goals"],
                    away_goals=labels["away_goals"],
                    corners=labels["corners"],
                    cards=labels["cards"],
                    player_shots=labels["player_shots"],
                    player_sot=labels["player_sot"],
                    player_scored=labels["player_scored"],
                    live_goal=labels["live_goal"],
                )
            )
            team_state[home_id].append((labels["home_goals"], labels["away_goals"], labels["home_corners"], labels["home_cards"]))
            team_state[away_id].append((labels["away_goals"], labels["home_goals"], labels["away_corners"], labels["away_cards"]))
        return tuple(rows)

    def load_competition_season(self, competition_id: int, season_id: int) -> tuple[TrainingRow, ...]:
        observation = self.provider.matches(competition_id, season_id)
        if not isinstance(observation.payload, list):
            return ()
        return self.build(observation.payload)


def snapshots_from_rows(rows: Iterable[TrainingRow], observed_at: datetime) -> tuple[FeatureSnapshot, ...]:
    return tuple(
        FeatureSnapshot(match_id=row.match_id, as_of=observed_at, features=row.features)
        for row in rows
    )


def _team(match: dict[str, Any], side: str) -> dict[str, Any]:
    team = match.get(side) or {}
    return {"id": team.get("team_id", team.get("id", "")), "team_name": team.get("team_name", team.get("name", ""))}


def _team_rates(history: deque[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    if not history:
        return 1.2, 1.2, 5.0, 2.0
    scored = mean(item[0] for item in history)
    conceded = mean(item[1] for item in history)
    corners = mean(item[2] for item in history)
    cards = mean(item[3] for item in history)
    return scored, conceded, corners, cards


def _event_labels(events: Iterable[dict[str, Any]], home: str, away: str) -> dict[str, Any]:
    goals = {home: 0, away: 0}
    corners = {home: 0, away: 0}
    cards = {home: 0, away: 0}
    player_shots: list[int] = []
    player_sot: list[int] = []
    player_goals: list[int] = []
    live_goal_events = 0
    for event in events:
        team = str((event.get("team") or {}).get("name", ""))
        event_type = str((event.get("type") or {}).get("name", ""))
        if event_type in {"Shot", "Goal"}:
            player_shots.append(1)
            outcome = str((event.get("shot") or {}).get("outcome", {}).get("name", ""))
            if outcome in {"Goal", "Saved To Post"}:
                player_sot.append(1)
            if outcome == "Goal":
                player_goals.append(1)
                if team in goals:
                    goals[team] += 1
                live_goal_events += 1
        if event_type == "Pass" and (event.get("pass") or {}).get("type", {}).get("name") == "Corner":
            if team in corners:
                corners[team] += 1
        card = (event.get("foul_committed") or {}).get("card", {}).get("name")
        if not card:
            card = (event.get("bad_behaviour") or {}).get("card", {}).get("name")
        if card and team in cards:
            cards[team] += 1
    shots = sum(player_shots)
    sot = sum(player_sot)
    scored = sum(player_goals)
    return {
        "home_goals": goals[home],
        "away_goals": goals[away],
        "corners": sum(corners.values()),
        "cards": sum(cards.values()),
        "home_corners": corners[home],
        "away_corners": corners[away],
        "home_cards": cards[home],
        "away_cards": cards[away],
        "player_shots": shots,
        "player_sot": sot,
        "player_scored": 1 if scored else 0,
        "player_shots_rate": shots / max(1, len(list(events))) if shots else 0.01,
        "player_sot_rate": sot / max(1, len(list(events))) if sot else 0.01,
        "player_goal_rate": scored / max(1, len(list(events))),
        "live_goal": 1 if live_goal_events else 0,
    }


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.min

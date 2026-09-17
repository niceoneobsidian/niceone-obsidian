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

    Match N receives only state accumulated from matches before N. Current-match
    events are used solely as labels and are applied to state after the row is
    emitted. This is the critical anti-look-ahead boundary for model fitting.
    """

    def __init__(self, provider: StatsBombOpenDataProvider | None = None, window: int = 8) -> None:
        self.provider = provider or StatsBombOpenDataProvider()
        self.window = max(1, window)

    def build(self, matches: Sequence[dict[str, Any]]) -> tuple[TrainingRow, ...]:
        ordered = sorted(matches, key=lambda match: _parse_datetime(match.get("match_date")))
        team_state: dict[str, deque[tuple[float, float, float, float]]] = defaultdict(lambda: deque(maxlen=self.window))
        player_state: deque[tuple[int, int, int]] = deque(maxlen=self.window * 20)
        rows: list[TrainingRow] = []
        for rank, match in enumerate(ordered):
            home = _team(match, "home")
            away = _team(match, "away")
            home_id, away_id = str(home["id"]), str(away["id"])
            home_prior = _team_rates(team_state[home_id])
            away_prior = _team_rates(team_state[away_id])
            prior_player_rates = _player_rates(player_state)
            events_observation = self.provider.events(int(match["match_id"]))
            event_rows = events_observation.payload if isinstance(events_observation.payload, list) else []
            labels = _event_labels(event_rows, home.get("team_name", ""), away.get("team_name", ""))
            features = MatchFeatures(
                home_attack=max(0.05, home_prior[0]),
                home_defense=max(0.05, home_prior[1]),
                away_attack=max(0.05, away_prior[0]),
                away_defense=max(0.05, away_prior[1]),
                expected_corners=max(0.1, home_prior[2] + away_prior[2]),
                expected_cards=max(0.1, home_prior[3] + away_prior[3]),
                player_shot_rate=prior_player_rates[0],
                player_sot_rate=prior_player_rates[1],
                player_goal_rate=prior_player_rates[2],
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
            player_state.extend(labels["player_history"])
        return tuple(rows)

    def load_competition_season(self, competition_id: int, season_id: int) -> tuple[TrainingRow, ...]:
        observation = self.provider.matches(competition_id, season_id)
        if not isinstance(observation.payload, list):
            return ()
        return self.build(observation.payload)


def snapshots_from_rows(rows: Iterable[TrainingRow], observed_at: datetime) -> tuple[FeatureSnapshot, ...]:
    return tuple(FeatureSnapshot(match_id=row.match_id, as_of=observed_at, features=row.features) for row in rows)


def _team(match: dict[str, Any], side: str) -> dict[str, Any]:
    team = match.get(side) or {}
    return {"id": team.get("team_id", team.get("id", "")), "team_name": team.get("team_name", team.get("name", ""))}


def _team_rates(history: deque[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    if not history:
        return 1.2, 1.2, 5.0, 2.0
    return (
        mean(item[0] for item in history),
        mean(item[1] for item in history),
        mean(item[2] for item in history),
        mean(item[3] for item in history),
    )


def _player_rates(history: deque[tuple[int, int, int]]) -> tuple[float, float, float]:
    if not history:
        return 1.5, 0.5, 0.15
    return (
        max(0.01, mean(item[0] for item in history)),
        max(0.01, mean(item[1] for item in history)),
        max(0.0, mean(item[2] for item in history)),
    )


def _event_labels(events: Sequence[dict[str, Any]], home: str, away: str) -> dict[str, Any]:
    goals = {home: 0, away: 0}
    corners = {home: 0, away: 0}
    cards = {home: 0, away: 0}
    player_history: list[tuple[int, int, int]] = []
    player_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    live_goal_events = 0
    for event in events:
        team = str((event.get("team") or {}).get("name", ""))
        player = str((event.get("player") or {}).get("name", "unknown"))
        event_type = str((event.get("type") or {}).get("name", ""))
        if event_type == "Shot":
            player_counts[player][0] += 1
            outcome = str((event.get("shot") or {}).get("outcome", {}).get("name", ""))
            if outcome in {"Goal", "Saved To Post", "Saved", "Blocked"}:
                player_counts[player][1] += 1
            if outcome == "Goal":
                player_counts[player][2] += 1
                if team in goals:
                    goals[team] += 1
                live_goal_events += 1
        if event_type == "Pass" and (event.get("pass") or {}).get("type", {}).get("name") == "Corner" and team in corners:
            corners[team] += 1
        card = (event.get("foul_committed") or {}).get("card", {}).get("name") or (event.get("bad_behaviour") or {}).get("card", {}).get("name")
        if card and team in cards:
            cards[team] += 1
    player_history.extend(tuple(values) for values in player_counts.values())
    return {
        "home_goals": goals[home],
        "away_goals": goals[away],
        "corners": sum(corners.values()),
        "cards": sum(cards.values()),
        "home_corners": corners[home],
        "away_corners": corners[away],
        "home_cards": cards[home],
        "away_cards": cards[away],
        "player_shots": sum(value[0] for value in player_counts.values()),
        "player_sot": sum(value[1] for value in player_counts.values()),
        "player_scored": int(any(value[2] > 0 for value in player_counts.values())),
        "live_goal": int(live_goal_events > 0),
        "player_history": player_history,
    }


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.min

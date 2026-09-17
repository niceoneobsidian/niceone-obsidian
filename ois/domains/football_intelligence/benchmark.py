"""Multi-match governed Football replay benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from .evaluation import CalibrationReport, evaluate_predictions
from .providers import StatsBombOpenDataProvider
from .replay import FootballReplay
from .schemas import FootballPrediction


@dataclass(frozen=True)
class FootballBenchmarkResult:
    """Immutable benchmark result with dataset and runtime coverage evidence."""

    competition_id: int
    season_id: int
    dataset_digest: str
    requested_matches: int
    evaluated_matches: int
    failed_matches: int
    skipped_matches: int
    metrics: CalibrationReport
    failures: tuple[str, ...]


class FootballReplayBenchmark:
    """Evaluate a historical corpus through the governed replay path."""

    def __init__(
        self,
        provider: StatsBombOpenDataProvider | None = None,
        replay: FootballReplay | None = None,
    ) -> None:
        self.provider = provider or StatsBombOpenDataProvider()
        self.replay = replay or FootballReplay()

    @staticmethod
    def _dataset_digest(matches: list[dict[str, Any]]) -> str:
        canonical = json.dumps(matches, sort_keys=True, separators=(",", ":"), default=str).encode()
        return sha256(canonical).hexdigest()

    def run(
        self,
        competition_id: int,
        season_id: int,
        *,
        match_ids: list[int] | None = None,
        limit: int | None = None,
        min_history_matches: int = 1,
    ) -> FootballBenchmarkResult:
        """Run selected historical matches without using their post-match data for prediction."""
        matches = self.provider.load_matches(competition_id, season_id)
        ordered = sorted(matches, key=self.provider._kickoff)
        selected = [
            match
            for match in ordered
            if match_ids is None or int(match.get("match_id", -1)) in set(match_ids)
        ]
        if limit is not None:
            selected = selected[:limit]

        predictions: list[FootballPrediction] = []
        outcomes: list[str] = []
        failures: list[str] = []
        skipped = 0
        for target in selected:
            target_id = int(target["match_id"])
            kickoff = self.provider._kickoff(target)
            historical = [m for m in ordered if self.provider._kickoff(m) < kickoff]
            team_ids = {
                str(target["home_team"]["home_team_id"]),
                str(target["away_team"]["away_team_id"]),
            }
            usable_history = sum(
                1
                for record in historical
                if str(record["home_team"]["home_team_id"]) in team_ids
                or str(record["away_team"]["away_team_id"]) in team_ids
            )
            if usable_history < min_history_matches:
                skipped += 1
                continue
            try:
                result = self.replay.run_statsbomb(competition_id, season_id, target_id, provider=self.provider)
                predictions.append(result.prediction)
                outcomes.append(self.provider._outcome(target))
            except (KeyError, TypeError, ValueError, OSError) as exc:
                failures.append(f"{target_id}:{type(exc).__name__}:{exc}")

        metrics = evaluate_predictions(predictions, outcomes)
        return FootballBenchmarkResult(
            competition_id=competition_id,
            season_id=season_id,
            dataset_digest=self._dataset_digest(matches),
            requested_matches=len(selected),
            evaluated_matches=metrics.count,
            failed_matches=len(failures),
            skipped_matches=skipped,
            metrics=metrics,
            failures=tuple(failures),
        )

"""Training orchestration boundary for historical fitting and live feature capture."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable, Sequence

from ois.domains.football_intelligence.feed_service import FootballFeedService, MatchFeatureSnapshot

from .historical import HistoricalCorpusBuilder
from .pipeline import FeatureSnapshot, HistoricalFeatureStore
from .training import FittedFootballModels, TrainingRow, fit_seven_models


@dataclass(frozen=True)
class TrainingArtifact:
    model_id: str
    created_at: datetime
    rows: int
    source_versions: tuple[str, ...]
    status: str


class FootballModelTrainingService:
    """Connect provider snapshots, feature storage and independent fitting."""

    def __init__(self, store: HistoricalFeatureStore, corpus_builder: HistoricalCorpusBuilder | None = None) -> None:
        self.store = store
        self.corpus_builder = corpus_builder or HistoricalCorpusBuilder()

    def ingest_live_snapshot(self, snapshot: MatchFeatureSnapshot) -> FeatureSnapshot:
        """Persist a provider observation as an append-only feature snapshot."""
        from .provider_bridge import ingest_provider_snapshot

        return ingest_provider_snapshot(self.store, snapshot)

    def fit_from_rows(self, rows: Sequence[TrainingRow]) -> tuple[FittedFootballModels, TrainingArtifact]:
        """Fit all seven models independently; promotion remains outside this service."""
        models = fit_seven_models(rows)
        artifact = TrainingArtifact(
            model_id="football-market-suite-trained-v1",
            created_at=datetime.now(UTC),
            rows=models.training_rows,
            source_versions=models.source_versions,
            status="candidate",
        )
        return models, artifact

    def fit_statsbomb_season(self, competition_id: int, season_id: int) -> tuple[FittedFootballModels, TrainingArtifact]:
        """Fetch an actual StatsBomb historical season and fit the market suite."""
        rows = self.corpus_builder.load_competition_season(competition_id, season_id)
        if len(rows) < 20:
            raise ValueError("historical sample is too small for governed fitting")
        return self.fit_from_rows(rows)


class LiveFootballSnapshotCollector:
    """Collect live provider state without silently creating historical truth."""

    def __init__(self, feed_service: FootballFeedService, trainer: FootballModelTrainingService) -> None:
        self.feed_service = feed_service
        self.trainer = trainer

    def collect(self) -> tuple[FeatureSnapshot, ...]:
        snapshots: list[FeatureSnapshot] = []
        for match in self.feed_service.live_matches():
            snapshot = self.feed_service.feature_snapshot(match)
            snapshots.append(self.trainer.ingest_live_snapshot(snapshot))
        return tuple(snapshots)

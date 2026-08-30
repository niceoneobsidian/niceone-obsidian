"""Kernel-neutral workflow specifications for football intelligence."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FootballWorkflow:
    workflow_id: str
    version: int
    steps: tuple[str, ...]


FOOTBALL_WORKFLOWS: tuple[FootballWorkflow, ...] = (
    FootballWorkflow(
        "football.predict", 1,
        ("football.ingest", "football.team_state", "football.player_state", "football.features",
         "football.predict_1x2", "football.simulate", "football.calibrate", "football.abstain"),
    ),
    FootballWorkflow(
        "football.backtest", 1,
        ("football.ingest", "football.features", "football.backtest", "football.calibrate"),
    ),
    FootballWorkflow(
        "football.live_prediction", 1,
        ("football.live_update", "football.simulate", "football.calibrate", "football.abstain"),
    ),
)


def workflow_manifest() -> list[dict[str, object]]:
    return [{"workflow_id": w.workflow_id, "version": w.version, "steps": list(w.steps)} for w in FOOTBALL_WORKFLOWS]

"""Regression tests for the Football Intelligence F0-F12 origin layer."""
from datetime import UTC, datetime, timedelta

from ois.domains.football_intelligence import (
    FixtureRecord, TeamStrengthModel, ValidatedBacktestEngine, WalkForwardEngine,
    evaluate, no_vig_probabilities, market_edge,
)


def fixture(i: int, home: str, away: str, hg: int, ag: int) -> FixtureRecord:
    return FixtureRecord(
        fixture_id=str(i), competition="TEST", kickoff_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
        home_team_id=home, home_team=home, away_team_id=away, away_team=away,
        home_goals=hg, away_goals=ag, home_xg=hg + 0.1, away_xg=ag + 0.1,
        status="finished", source_id="test", observed_at=datetime.now(UTC),
    )


def test_team_strength_updates_after_completed_result() -> None:
    model = TeamStrengthModel()
    before = model.rating("A")
    model.update(fixture(1, "A", "B", 2, 0))
    assert model.rating("A") > before
    assert model.snapshot("A").matches == 1


def test_no_vig_market_edge() -> None:
    probs = no_vig_probabilities((2.0, 3.5, 4.0))
    assert probs is not None
    assert abs(sum(probs) - 1.0) < 1e-9
    edge = market_edge((0.50, 0.25, 0.25), (2.0, 3.5, 4.0))
    assert edge["home"] > 0


def test_chronological_backtest() -> None:
    rows = [fixture(i, "A" if i % 2 else "B", "B" if i % 2 else "A", 2, 0) for i in range(1, 8)]
    report = ValidatedBacktestEngine().run(rows)
    assert report.count == 7
    assert report.status == "EVALUATED"


def test_walk_forward_requires_history() -> None:
    rows = [fixture(i, "A", "B", 1, 0) for i in range(10)]
    assert WalkForwardEngine().run(rows, min_train=20).status == "INSUFFICIENT_DATA"


def test_evaluation_alignment_and_metrics() -> None:
    rows = [fixture(i, "A", "B", 1, 0) for i in range(1, 4)]
    model = ValidatedBacktestEngine()
    report = model.run(rows)
    assert report.count == 3
    assert 0 <= report.accuracy <= 1
    assert report.brier >= 0


def test_empty_evaluation_is_explicit() -> None:
    assert evaluate([], []).status == "INSUFFICIENT_DATA"

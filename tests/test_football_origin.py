"""Origin-layer regression tests for F2-F9 and F12."""
from datetime import UTC, datetime, timedelta

from ois.domains.football_intelligence.origin import (
    BacktestEngine,
    FixtureRecord,
    ProbabilityCalibrator,
    TeamStrengthModel,
    WalkForwardEvaluator,
    calibration_report,
    market_edge,
    no_vig_probabilities,
    propose_evolution,
)


def fixture(i: int, home: str, away: str, hg: int, ag: int) -> FixtureRecord:
    return FixtureRecord(
        fixture_id=str(i), competition="TEST", kickoff_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
        home_team_id=home, home_team=home, away_team_id=away, away_team=away,
        home_goals=hg, away_goals=ag, home_xg=hg + 0.1, away_xg=ag + 0.1, status="finished", source_id="test",
        observed_at=datetime.now(UTC),
    )


def test_team_strength_updates_only_completed() -> None:
    model = TeamStrengthModel()
    before = model.rating("A")
    model.update(fixture(1, "A", "B", 2, 0))
    assert model.rating("A") > before
    assert model.snapshot("A").matches == 1


def test_no_vig_and_market_edge() -> None:
    probs = no_vig_probabilities((2.0, 3.5, 4.0))
    assert probs is not None
    assert abs(sum(probs) - 1.0) < 1e-9
    edge = market_edge((0.50, 0.25, 0.25), (2.0, 3.5, 4.0))
    assert edge["home"] > 0


def test_calibrator_returns_normalized_probabilities() -> None:
    cal = ProbabilityCalibrator()
    cal.fit([(0.7, 0.2, 0.1), (0.6, 0.3, 0.1), (0.1, 0.2, 0.7)], ["home", "home", "away"])
    transformed = cal.transform((0.5, 0.3, 0.2))
    assert abs(sum(transformed) - 1.0) < 1e-9


def test_backtest_is_chronological() -> None:
    rows = [fixture(i, "A" if i % 2 else "B", "B" if i % 2 else "A", 2, 0) for i in range(1, 8)]
    report = BacktestEngine().run(rows)
    assert report.count == 7
    assert report.status == "EVALUATED"


def test_walk_forward_requires_history() -> None:
    rows = [fixture(i, "A", "B", 1, 0) for i in range(10)]
    assert WalkForwardEvaluator().evaluate(rows, min_train=20).status == "INSUFFICIENT_DATA"


def test_evolution_proposal_is_reversible() -> None:
    baseline = BacktestEngine().run([fixture(i, "A", "B", 1, 0) for i in range(1, 5)])
    proposal = propose_evolution("v1", "v2", baseline, baseline)
    assert proposal.requires_approval is True
    assert proposal.reversible is True


def test_calibration_report() -> None:
    engine = BacktestEngine()
    rows = [fixture(i, "A", "B", 1, 0) for i in range(1, 4)]
    preds = [engine.predict(row) for row in rows]
    report = calibration_report(preds, ["home"] * len(preds))
    assert report.count == 3

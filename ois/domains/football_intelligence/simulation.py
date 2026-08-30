"""Monte Carlo football match simulation.

The simulator is deterministic when a seed is supplied and uses a correlated
Poisson construction so the output can be reproduced and audited. It is a
simulation layer, not a claim that 10,000 iterations create extra predictive
information beyond the quality of the input xG distribution.
"""
from __future__ import annotations

import random
from collections import Counter

from .schemas import SimulationResult


def _poisson(rng: random.Random, lam: float) -> int:
    # Knuth's method is dependency-free and sufficient for football scoring rates.
    threshold = pow(2.718281828459045, -max(lam, 0.0))
    product = 1.0
    count = 0
    while product > threshold:
        count += 1
        product *= rng.random()
    return count - 1


def simulate_match(
    expected_home_goals: float,
    expected_away_goals: float,
    *,
    iterations: int = 10_000,
    correlation: float = 0.0,
    seed: int | None = None,
) -> SimulationResult:
    """Simulate a match and return calibrated empirical outcome frequencies.

    ``correlation`` is a conservative shared-goal component in [0, 0.5]. A
    non-zero value models common match-state shocks without pretending the two
    scoring processes are independent.
    """
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    if expected_home_goals < 0 or expected_away_goals < 0:
        raise ValueError("expected goals must be non-negative")
    if not 0.0 <= correlation <= 0.5:
        raise ValueError("correlation must be between 0 and 0.5")

    rng = random.Random(seed)
    shared = min(expected_home_goals, expected_away_goals) * correlation
    home_lambda = max(expected_home_goals - shared, 0.0)
    away_lambda = max(expected_away_goals - shared, 0.0)
    outcomes = Counter()
    scores = Counter()

    for _ in range(iterations):
        common = _poisson(rng, shared) if shared else 0
        home = _poisson(rng, home_lambda) + common
        away = _poisson(rng, away_lambda) + common
        scores[f"{home}-{away}"] += 1
        if home > away:
            outcomes["home"] += 1
        elif home == away:
            outcomes["draw"] += 1
        else:
            outcomes["away"] += 1

    total = float(iterations)
    most_likely_score, count = scores.most_common(1)[0]
    return SimulationResult(
        iterations=iterations,
        home_win=outcomes["home"] / total,
        draw=outcomes["draw"] / total,
        away_win=outcomes["away"] / total,
        expected_home_goals=sum(int(score.split("-")[0]) * n for score, n in scores.items()) / total,
        expected_away_goals=sum(int(score.split("-")[1]) * n for score, n in scores.items()) / total,
        most_likely_score=most_likely_score,
        scoreline_distribution={score: n / total for score, n in scores.items()},
        seed=seed,
    )

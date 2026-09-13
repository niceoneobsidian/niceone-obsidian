from random import Random

import pytest

from ois.domains.social_intelligence.closed_loop import (
    ConversionEvent,
    OptimizationConfig,
    attribute_events,
    calibrate_learning_state,
    choose_optimization_strategy,
    create_tracking_token,
    evaluate_g12_boundary,
    weighted_centroid,
)


def test_g7_tracking_token_is_deterministic_and_secret_bound() -> None:
    first = create_tracking_token(
        post_id="post-1", genome_id="genome-1", secret=b"secret"
    )
    second = create_tracking_token(
        post_id="post-1", genome_id="genome-1", secret=b"secret"
    )
    different_secret = create_tracking_token(
        post_id="post-1", genome_id="genome-1", secret=b"other"
    )
    assert first == second
    assert first != different_secret
    assert len(first) == 64


def test_g7_unknown_tracking_tokens_are_not_guessed() -> None:
    event = ConversionEvent("known", "checkout_completed", 120.0)
    records = attribute_events(
        [event], {"known": ("post-1", "genome-1", "execution-1")}
    )
    assert records[0].post_id == "post-1"
    assert records[0].revenue == 120.0
    assert attribute_events(
        [ConversionEvent("unknown", "signup", 1.0)], {}
    ) == ()


def test_g10_weighted_centroid_normalizes() -> None:
    centroid = weighted_centroid([[1.0, 0.0], [0.0, 1.0]], [3.0, 1.0])
    assert centroid[0] > centroid[1]
    assert pytest.approx(sum(value * value for value in centroid)) == 1.0


def test_g10_calibration_is_evidence_bounded() -> None:
    state = calibrate_learning_state(
        platform="tiktok",
        objective="maximize_revenue",
        examples=[
            ("post-1", [1.0, 0.0], 100.0),
            ("post-2", [0.0, 1.0], 0.0),
        ],
    )
    assert state is not None
    assert state.sample_size == 1
    assert state.total_revenue == 100.0
    assert state.source_post_ids == ("post-1",)


def test_g11_exploit_and_explore_are_bounded() -> None:
    config = OptimizationConfig(exploration_epsilon=0.5, generation_temperature=0.4, top_k_precedents=3)
    exploit = choose_optimization_strategy(config, rng=Random(2))
    explore = choose_optimization_strategy(config, rng=Random(1))
    assert exploit["execution_mode"] == "exploit"
    assert exploit["top_k_precedents"] == 3
    assert explore["execution_mode"] == "explore"
    assert explore["temperature"] <= 2.0
    assert explore["top_k_precedents"] == 0


def test_g12_pauses_on_queue_age_boundary() -> None:
    state = evaluate_g12_boundary(queue_oldest_age_seconds=3600, consecutive_failures=0)
    assert state.state == "PAUSED"
    assert not state.execution_allowed
    assert state.reason == "queue_oldest_age_boundary_breached"


def test_g12_pauses_on_repeated_failure_boundary() -> None:
    state = evaluate_g12_boundary(queue_oldest_age_seconds=10, consecutive_failures=5)
    assert state.state == "PAUSED"
    assert state.reason == "consecutive_failure_boundary_breached"


def test_g12_allows_execution_inside_bounds() -> None:
    state = evaluate_g12_boundary(queue_oldest_age_seconds=10, consecutive_failures=1)
    assert state.execution_allowed
    assert state.reason == "within_operational_bounds"

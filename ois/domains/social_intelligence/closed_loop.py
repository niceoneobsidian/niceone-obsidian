"""Governed G7-G12 social intelligence closed-loop primitives.

This module intentionally contains provider-neutral contracts and deterministic
algorithms. AWS/SQS/ECS/Step Functions and social-platform adapters remain
execution providers behind OIS Tool/Capability contracts; they are not granted
new authority here.

Flow:
    G4 Genome -> G7 Attribution -> G10 Learning -> G11 Optimization
              -> G6/G8 decision boundary -> G2 execution
              -> G12 bounded operations / circuit breaker

The module is safe to use as a contract/integration-test oracle because it does
not perform network calls, mutate production state, or silently promote learned
parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import math
import random
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ConversionEvent:
    """Normalized bottom-of-funnel event captured by G7."""

    tracking_token: str
    event_name: str
    revenue: float = 0.0
    timestamp: str | None = None


@dataclass(frozen=True)
class AttributionRecord:
    """Conversion mapped to a content genome and execution identity."""

    tracking_token: str
    post_id: str
    event_name: str
    revenue: float
    genome_id: str | None
    execution_id: str | None


@dataclass(frozen=True)
class LearningState:
    """Versioned G10 state candidate; never implies production activation."""

    platform: str
    objective: str
    centroid: tuple[float, ...]
    sample_size: int
    total_revenue: float
    source_post_ids: tuple[str, ...]
    version: str = "g10.v1"


@dataclass(frozen=True)
class OptimizationConfig:
    """Bounded G11 exploration/exploitation parameters."""

    exploration_epsilon: float = 0.20
    generation_temperature: float = 0.45
    top_k_precedents: int = 3

    def __post_init__(self) -> None:
        if not 0.0 <= self.exploration_epsilon <= 1.0:
            raise ValueError("exploration_epsilon must be in [0, 1]")
        if not 0.0 <= self.generation_temperature <= 2.0:
            raise ValueError("generation_temperature must be in [0, 2]")
        if not 1 <= self.top_k_precedents <= 10:
            raise ValueError("top_k_precedents must be in [1, 10]")


@dataclass(frozen=True)
class BoundaryState:
    """G12 operational boundary decision."""

    state: str
    reason: str
    queue_oldest_age_seconds: float
    consecutive_failures: int
    version: str = "g12.v1"

    @property
    def execution_allowed(self) -> bool:
        return self.state == "ACTIVE"


def create_tracking_token(
    *, post_id: str, genome_id: str, secret: bytes, version: str = "g7.v1"
) -> str:
    """Create a deterministic, non-reversible attribution token.

    HMAC prevents callers from treating a plain post/genome identifier as a
    public tracking credential. The secret must come from a governed secret
    provider at runtime.
    """
    message = f"{version}:{post_id}:{genome_id}".encode()
    return hmac.new(secret, message, sha256).hexdigest()


def attribute_events(
    events: Sequence[ConversionEvent],
    post_lookup: Mapping[str, tuple[str, str | None, str | None]],
) -> tuple[AttributionRecord, ...]:
    """Resolve G7 events through a deterministic token -> content lookup.

    ``post_lookup[token]`` is ``(post_id, genome_id, execution_id)``.
    Unknown tokens are intentionally omitted rather than guessed.
    """
    records: list[AttributionRecord] = []
    for event in events:
        target = post_lookup.get(event.tracking_token)
        if target is None:
            continue
        post_id, genome_id, execution_id = target
        records.append(
            AttributionRecord(
                tracking_token=event.tracking_token,
                post_id=post_id,
                event_name=event.event_name,
                revenue=float(event.revenue),
                genome_id=genome_id,
                execution_id=execution_id,
            )
        )
    return tuple(records)


def weighted_centroid(
    vectors: Sequence[Sequence[float]], weights: Sequence[float]
) -> tuple[float, ...]:
    """Return a unit-normalized revenue-weighted centroid."""
    if not vectors or len(vectors) != len(weights):
        raise ValueError("vectors and weights must be non-empty and equal length")
    dimension = len(vectors[0])
    if dimension == 0 or any(len(vector) != dimension for vector in vectors):
        raise ValueError("all vectors must have the same non-zero dimension")
    if any(weight < 0 for weight in weights) or not any(weights):
        raise ValueError("weights must be non-negative and have positive total")

    total_weight = float(sum(weights))
    centroid = tuple(
        sum(vector[i] * weight for vector, weight in zip(vectors, weights)) / total_weight
        for i in range(dimension)
    )
    norm = math.sqrt(sum(value * value for value in centroid))
    if norm == 0.0:
        return tuple(0.0 for _ in centroid)
    return tuple(value / norm for value in centroid)


def calibrate_learning_state(
    *,
    platform: str,
    objective: str,
    examples: Sequence[tuple[str, Sequence[float], float]],
) -> LearningState | None:
    """Create a G10 candidate from revenue-bearing attributed examples."""
    eligible = [item for item in examples if item[2] > 0]
    if not eligible:
        return None
    post_ids = tuple(item[0] for item in eligible)
    vectors = [item[1] for item in eligible]
    weights = [float(item[2]) for item in eligible]
    return LearningState(
        platform=platform,
        objective=objective,
        centroid=weighted_centroid(vectors, weights),
        sample_size=len(eligible),
        total_revenue=sum(weights),
        source_post_ids=post_ids,
    )


def choose_optimization_strategy(
    config: OptimizationConfig, *, rng: random.Random | None = None
) -> dict[str, object]:
    """Choose bounded explore/exploit behavior for G11."""
    generator = rng or random.Random()
    explore = generator.random() < config.exploration_epsilon
    if explore:
        return {
            "execution_mode": "explore",
            "temperature": min(config.generation_temperature * 1.5, 2.0),
            "top_k_precedents": 0,
        }
    return {
        "execution_mode": "exploit",
        "temperature": config.generation_temperature,
        "top_k_precedents": config.top_k_precedents,
    }


def evaluate_g12_boundary(
    *,
    queue_oldest_age_seconds: float,
    consecutive_failures: int,
    max_oldest_age_seconds: float = 3600.0,
    max_consecutive_failures: int = 5,
) -> BoundaryState:
    """Apply a hard, deterministic production execution boundary.

    The breaker is deliberately fail-closed: either queue age or repeated
    failures beyond the configured bound pauses autonomous execution.
    """
    if queue_oldest_age_seconds >= max_oldest_age_seconds:
        return BoundaryState(
            state="PAUSED",
            reason="queue_oldest_age_boundary_breached",
            queue_oldest_age_seconds=queue_oldest_age_seconds,
            consecutive_failures=consecutive_failures,
        )
    if consecutive_failures >= max_consecutive_failures:
        return BoundaryState(
            state="PAUSED",
            reason="consecutive_failure_boundary_breached",
            queue_oldest_age_seconds=queue_oldest_age_seconds,
            consecutive_failures=consecutive_failures,
        )
    return BoundaryState(
        state="ACTIVE",
        reason="within_operational_bounds",
        queue_oldest_age_seconds=queue_oldest_age_seconds,
        consecutive_failures=consecutive_failures,
    )

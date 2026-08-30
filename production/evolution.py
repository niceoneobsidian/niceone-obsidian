"""Evidence-gated measurement, canary and learning lifecycle."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class Measurement:
    name: str
    value: float


@dataclass(frozen=True)
class Evaluation:
    candidate: str
    score: float
    baseline: float
    passed: bool
    reason: str


@dataclass(frozen=True)
class CanaryDecision:
    candidate: str
    traffic_percent: int
    success_rate: float
    latency_ms: float
    passed: bool


class LearningLoop:
    """Turns measured outcomes into candidates without self-authorizing promotion."""

    def evaluate(self, candidate: str, measurements: Iterable[Measurement], *, baseline: float, minimum_score: float) -> Evaluation:
        values = [m.value for m in measurements]
        if not values:
            return Evaluation(candidate, 0.0, baseline, False, "no measurements")
        score = mean(values)
        return Evaluation(candidate, score, baseline, score >= minimum_score, "score gate")

    def candidate(self, candidate: str, evaluation: Evaluation, *, approved: bool = False) -> str:
        if not evaluation.passed:
            return "REJECTED"
        if not approved:
            return "PENDING_APPROVAL"
        return "APPROVED"


class CanaryController:
    def __init__(self, *, minimum_success_rate: float = 0.99, maximum_latency_ms: float = 1000.0) -> None:
        self.minimum_success_rate = minimum_success_rate
        self.maximum_latency_ms = maximum_latency_ms

    def decide(self, candidate: str, traffic_percent: int, *, successes: int, total: int, latency_ms: float) -> CanaryDecision:
        if not 1 <= traffic_percent <= 100:
            raise ValueError("traffic_percent must be between 1 and 100")
        success_rate = successes / total if total else 0.0
        passed = success_rate >= self.minimum_success_rate and latency_ms <= self.maximum_latency_ms
        return CanaryDecision(candidate, traffic_percent, success_rate, latency_ms, passed)

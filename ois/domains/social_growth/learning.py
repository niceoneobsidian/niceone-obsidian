"""Closed-loop learning primitives for Social Growth.

This layer produces proposals only. Promotion or mutation remains an OIS
policy/evaluation decision.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LearningObservation:
    strategy_id: str
    metric: str
    baseline: float
    observed: float
    sample_size: int

    @property
    def delta(self) -> float:
        return self.observed - self.baseline


@dataclass(frozen=True)
class LearningProposal:
    strategy_id: str
    action: str
    delta: float
    confidence: float
    requires_evaluation: bool = True


def propose_learning(observation: LearningObservation) -> LearningProposal:
    """Turn measured performance into a reversible optimization proposal."""
    if observation.sample_size <= 0:
        return LearningProposal(observation.strategy_id, "collect_more_data", 0.0, 0.0)
    if observation.delta > 0:
        action = "retain_or_test_scale"
    elif observation.delta < 0:
        action = "revise_or_test_variant"
    else:
        action = "collect_more_data"
    confidence = min(1.0, 0.4 + min(observation.sample_size, 1000) / 2500)
    return LearningProposal(
        strategy_id=observation.strategy_id,
        action=action,
        delta=observation.delta,
        confidence=confidence,
    )

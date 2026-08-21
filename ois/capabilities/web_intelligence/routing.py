from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .engines import AcquisitionEngine
from .models import WebIntelligenceRequest


@dataclass
class RouteLearner:
    """In-memory success-rate memory used by the router.

    Persistence belongs to OIS Memory/Learning. The capability only consumes
    this small interface so it can later be replaced by durable learning.
    """

    outcomes: dict[str, tuple[int, int]] = field(default_factory=dict)

    def score(self, engine_name: str) -> float:
        success, total = self.outcomes.get(engine_name, (0, 0))
        return (success / total) if total else 0.5

    def record(self, engine_name: str, success: bool) -> None:
        ok, total = self.outcomes.get(engine_name, (0, 0))
        self.outcomes[engine_name] = (ok + int(success), total + 1)


@dataclass
class AdaptiveRouter:
    engines: Sequence[AcquisitionEngine]
    learner: RouteLearner = field(default_factory=RouteLearner)

    def candidates(self, request: WebIntelligenceRequest) -> list[AcquisitionEngine]:
        candidates = [engine for engine in self.engines if engine.can_handle(request)]
        if request.preferred_engine:
            preferred = [e for e in candidates if e.name == request.preferred_engine]
            others = [e for e in candidates if e.name != request.preferred_engine]
            candidates = preferred + others
        return sorted(candidates, key=lambda e: self.learner.score(e.name), reverse=True)

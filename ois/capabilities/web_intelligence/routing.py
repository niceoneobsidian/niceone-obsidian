from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .engines import AcquisitionEngine
from .models import WebIntelligenceRequest


@dataclass
class RouteLearner:
    outcomes: dict[str, tuple[int, int]] = field(default_factory=dict)

    def score(self, name: str) -> float:
        success, total = self.outcomes.get(name, (0, 0))
        return success / total if total else 0.5

    def record(self, name: str, success: bool) -> None:
        current_success, current_total = self.outcomes.get(name, (0, 0))
        self.outcomes[name] = (
            current_success + int(success),
            current_total + 1,
        )


@dataclass
class AdaptiveRouter:
    engines: Sequence[AcquisitionEngine]
    learner: RouteLearner = field(default_factory=RouteLearner)

    def candidates(self, request: WebIntelligenceRequest) -> list[AcquisitionEngine]:
        candidates = [engine for engine in self.engines if engine.can_handle(request)]
        if request.preferred_engine:
            candidates.sort(key=lambda engine: engine.name != request.preferred_engine)
        else:
            candidates.sort(key=lambda engine: self.learner.score(engine.name), reverse=True)
        return candidates

"""Learning produces candidates; it does not deploy mutations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LearningCandidate:
    candidate_id: str
    evidence: tuple[str, ...]
    proposed_change: str


class LearningPlane:
    def propose(self, candidate_id: str, evidence: tuple[str, ...], proposed_change: str) -> LearningCandidate:
        if not evidence:
            raise ValueError("learning requires evidence")
        return LearningCandidate(candidate_id, evidence, proposed_change)

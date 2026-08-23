"""Versioned, approval-gated evolution boundary."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class EvolutionCandidate:
    candidate_id: str
    version: str
    evidence: tuple[str, ...]
    approved: bool = False

class EvolutionPlane:
    def approve(self, candidate: EvolutionCandidate) -> EvolutionCandidate:
        if not candidate.evidence:
            raise ValueError("evolution requires evidence")
        return EvolutionCandidate(candidate.candidate_id, candidate.version, candidate.evidence, True)

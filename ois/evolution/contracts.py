"""Controlled optimization and evolution contracts."""
from dataclasses import dataclass

@dataclass(frozen=True)
class EvolutionCandidate:
    candidate_id: str
    baseline: str
    evidence_ref: str
    approval_required: bool = True

@dataclass(frozen=True)
class PromotionDecision:
    candidate_id: str
    approved: bool
    rollback_plan: str

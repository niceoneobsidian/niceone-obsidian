"""Evidence-gated, reversible evolution proposals for OIS."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EvolutionState(StrEnum):
    PROPOSED = "proposed"
    EVALUATED = "evaluated"
    APPROVAL_REQUIRED = "approval_required"
    CANARY = "canary"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


@dataclass(frozen=True)
class EvolutionProposal:
    proposal_id: str
    target: str
    from_version: str
    candidate_version: str
    evidence_refs: tuple[str, ...]
    score: float | None = None
    state: EvolutionState = EvolutionState.PROPOSED


class ControlledEvolution:
    """State machine that separates learning from production mutation."""

    def __init__(self) -> None:
        self._items: dict[str, EvolutionProposal] = {}

    def propose(self, proposal: EvolutionProposal) -> EvolutionProposal:
        if proposal.proposal_id in self._items:
            raise ValueError(f"proposal already exists: {proposal.proposal_id}")
        if not proposal.evidence_refs:
            raise ValueError("evolution proposal requires evidence references")
        self._items[proposal.proposal_id] = proposal
        return proposal

    def evaluate(self, proposal_id: str, score: float, minimum: float = 0.0) -> EvolutionProposal:
        proposal = self._items[proposal_id]
        if not 0.0 <= score <= 1.0:
            raise ValueError("evolution score must be between 0 and 1")
        state = EvolutionState.EVALUATED if score >= minimum else EvolutionState.REJECTED
        updated = EvolutionProposal(
            proposal.proposal_id, proposal.target, proposal.from_version,
            proposal.candidate_version, proposal.evidence_refs, score, state,
        )
        self._items[proposal_id] = updated
        return updated

    def approve(self, proposal_id: str, *, actor: str) -> EvolutionProposal:
        proposal = self._items[proposal_id]
        if proposal.state is not EvolutionState.EVALUATED:
            raise ValueError("only evaluated proposals may be approved")
        if not actor:
            raise PermissionError("approval requires an authenticated actor")
        updated = EvolutionProposal(
            proposal.proposal_id, proposal.target, proposal.from_version,
            proposal.candidate_version, proposal.evidence_refs, proposal.score,
            EvolutionState.APPROVAL_REQUIRED,
        )
        self._items[proposal_id] = updated
        return updated

    def canary(self, proposal_id: str) -> EvolutionProposal:
        proposal = self._items[proposal_id]
        if proposal.state is not EvolutionState.APPROVAL_REQUIRED:
            raise ValueError("proposal requires approval before canary")
        updated = EvolutionProposal(
            proposal.proposal_id, proposal.target, proposal.from_version,
            proposal.candidate_version, proposal.evidence_refs, proposal.score,
            EvolutionState.CANARY,
        )
        self._items[proposal_id] = updated
        return updated

    def promote(self, proposal_id: str, *, rollback_verified: bool) -> EvolutionProposal:
        proposal = self._items[proposal_id]
        if proposal.state is not EvolutionState.CANARY:
            raise ValueError("only canary proposals may be promoted")
        if not rollback_verified:
            raise PermissionError("promotion requires verified rollback capability")
        updated = EvolutionProposal(
            proposal.proposal_id, proposal.target, proposal.from_version,
            proposal.candidate_version, proposal.evidence_refs, proposal.score,
            EvolutionState.PROMOTED,
        )
        self._items[proposal_id] = updated
        return updated

    def rollback(self, proposal_id: str) -> EvolutionProposal:
        proposal = self._items[proposal_id]
        if proposal.state not in {EvolutionState.CANARY, EvolutionState.PROMOTED}:
            raise ValueError("proposal is not active")
        updated = EvolutionProposal(
            proposal.proposal_id, proposal.target, proposal.from_version,
            proposal.candidate_version, proposal.evidence_refs, proposal.score,
            EvolutionState.ROLLED_BACK,
        )
        self._items[proposal_id] = updated
        return updated

from __future__ import annotations
from dataclasses import dataclass,field
from enum import StrEnum
from .contracts import VersionRef,utc_now
class EvolutionState(StrEnum): PROPOSED="proposed"; EVALUATED="evaluated"; APPROVED="approved"; CANARY="canary"; PROMOTED="promoted"; ROLLED_BACK="rolled_back"
@dataclass(frozen=True)
class EvolutionCandidate:
    candidate_id:str; component:VersionRef; change:dict[str,object]; evidence_ids:tuple[str,...]; evaluation_passed:bool=False; approval_granted:bool=False; state:EvolutionState=EvolutionState.PROPOSED; created_at:object=field(default_factory=utc_now)
class EvolutionRegistry:
    def __init__(self)->None:self._items:dict[str,EvolutionCandidate]={}
    def propose(self,component:VersionRef,change:dict[str,object],*,evidence_ids:tuple[str,...])->EvolutionCandidate:
        if not evidence_ids: raise ValueError("evolution requires evidence")
        import uuid
        item=EvolutionCandidate(str(uuid.uuid4()),component,dict(change),evidence_ids);self._items[item.candidate_id]=item;return item
    def evaluate(self,candidate_id:str,passed:bool)->EvolutionCandidate:
        item=self._items[candidate_id]; updated=EvolutionCandidate(item.candidate_id,item.component,item.change,item.evidence_ids,passed,item.approval_granted,EvolutionState.EVALUATED if passed else EvolutionState.PROPOSED,item.created_at);self._items[candidate_id]=updated;return updated
    def approve(self,candidate_id:str)->EvolutionCandidate:
        item=self._items[candidate_id]
        if not item.evaluation_passed: raise PermissionError("candidate must pass evaluation before approval")
        updated=EvolutionCandidate(item.candidate_id,item.component,item.change,item.evidence_ids,True,True,EvolutionState.APPROVED,item.created_at);self._items[candidate_id]=updated;return updated
    def promote(self,candidate_id:str)->EvolutionCandidate:
        item=self._items[candidate_id]
        if not item.approval_granted: raise PermissionError("candidate requires approval")
        updated=EvolutionCandidate(item.candidate_id,item.component,item.change,item.evidence_ids,True,True,EvolutionState.PROMOTED,item.created_at);self._items[candidate_id]=updated;return updated

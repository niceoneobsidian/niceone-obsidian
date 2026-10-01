from __future__ import annotations
from dataclasses import dataclass,field
from .contracts import PlatformIdentity,VersionRef,utc_now
@dataclass(frozen=True)
class LearningRecord:
    learning_id: str
    identity: PlatformIdentity
    hypothesis: str
    evidence_ids: tuple[str,...]
    outcome_ids: tuple[str,...]
    confidence: float
    strategy: VersionRef|None=None
    created_at: object=field(default_factory=utc_now)
class LearningStore:
    def __init__(self)->None: self._records:dict[str,LearningRecord]={}
    def record(self,identity:PlatformIdentity,hypothesis:str,*,evidence_ids:tuple[str,...],outcome_ids:tuple[str,...],confidence:float,strategy:VersionRef|None=None)->LearningRecord:
        if not hypothesis.strip(): raise ValueError("hypothesis is required")
        if not evidence_ids: raise ValueError("learning requires evidence")
        if not 0<=confidence<=1: raise ValueError("confidence must be between 0 and 1")
        import uuid
        item=LearningRecord(str(uuid.uuid4()),identity,hypothesis,evidence_ids,outcome_ids,confidence,strategy); self._records[item.learning_id]=item; return item
    def list(self,tenant_id:str)->tuple[LearningRecord,...]: return tuple(x for x in self._records.values() if x.identity.tenant_id==tenant_id)

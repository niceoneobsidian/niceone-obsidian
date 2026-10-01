from __future__ import annotations
from dataclasses import dataclass,field
from .contracts import Lineage,PlatformIdentity,utc_now
@dataclass(frozen=True)
class OutcomeEvent:
    outcome_id: str
    identity: PlatformIdentity
    outcome_type: str
    value: object
    lineage: Lineage
    verified: bool
    observed_at: object = field(default_factory=utc_now)
class OutcomeStore:
    def __init__(self)->None: self._items: dict[str,OutcomeEvent]={}
    def record(self,identity: PlatformIdentity,outcome_type: str,value: object,*,parent_ids: tuple[str,...]=(),verified: bool=False)->OutcomeEvent:
        import uuid
        oid=str(uuid.uuid4()); event=OutcomeEvent(oid,identity,outcome_type,value,Lineage(oid,parent_ids),verified)
        self._items[oid]=event; return event
    def verified(self,tenant_id: str)->tuple[OutcomeEvent,...]: return tuple(x for x in self._items.values() if x.identity.tenant_id==tenant_id and x.verified)

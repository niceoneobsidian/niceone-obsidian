"""Bounded secret rotation policy and workload identity contract."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC,datetime,timedelta
from typing import Protocol
@dataclass(frozen=True)
class RotationPolicy:
    max_age_days:int=90
    warning_days:int=14
@dataclass(frozen=True)
class RotationResult:
    credential_id:str
    rotated_at:datetime
    version:str
class RotatableCredentialStore(Protocol):
    def rotate(self,credential_id:str)->RotationResult: ...
class RotationService:
    def __init__(self,store:RotatableCredentialStore,policy:RotationPolicy|None=None)->None:self.store=store;self.policy=policy or RotationPolicy()
    def due(self,created_at:datetime,*,now:datetime|None=None)->bool:return (now or datetime.now(UTC))>=created_at+timedelta(days=self.policy.max_age_days)
    def rotate_if_due(self,credential_id:str,created_at:datetime,*,now:datetime|None=None)->RotationResult|None:
        return self.store.rotate(credential_id) if self.due(created_at,now=now) else None
class WorkloadIdentityProvider(Protocol):
    def issue(self,workload:str,audience:str)->tuple[str,datetime]: ...

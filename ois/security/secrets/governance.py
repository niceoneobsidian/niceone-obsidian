"""P4 governance and P5 agent security."""
from __future__ import annotations
import secrets
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from fnmatch import fnmatch
from typing import Callable,Protocol
from .core import Environment,SecretClassification
@dataclass(frozen=True,slots=True)
class PolicyRule:
    subject:str; environments:frozenset[Environment]; services:frozenset[str]; scopes:frozenset[str]
    max_classification:SecretClassification=SecretClassification.SECRET; allow:bool=True
_ORDER={SecretClassification.PUBLIC:0,SecretClassification.INTERNAL:1,SecretClassification.SENSITIVE:2,SecretClassification.SECRET:3,SecretClassification.CRITICAL:4}
class PolicyEngine:
    def __init__(self,rules=None): self.rules=rules or []
    def authorize_secret(self,m,c):
        for r in self.rules:
            if not r.allow or not fnmatch(c.actor_id,r.subject) or c.environment not in r.environments: continue
            if r.services and m.service_id not in r.services: continue
            if _ORDER[m.classification]>_ORDER[r.max_classification]: continue
            if r.scopes and not (c.scopes&r.scopes): continue
            return
        raise PermissionError(f"secret access denied: {m.name}")
@dataclass(frozen=True,slots=True)
class Role: name:str; permissions:frozenset[str]
class Rbac:
    def __init__(self,roles=None): self.roles=roles or {}
    def allows(self,role,permission): return permission in self.roles.get(role,Role(role,frozenset())).permissions
@dataclass(frozen=True,slots=True)
class WorkloadIdentity:
    workload_id:str; service_id:str; environment:str; issuer:str; subject:str; expires_at:datetime
class WorkloadIdentityProvider(Protocol):
    def authenticate(self,workload_id:str)->WorkloadIdentity: ...
@dataclass(frozen=True,slots=True)
class AccessSignal:
    actor_id:str; secret_id:str; occurred_at:datetime; source_ip:str|None; allowed:bool
class AnomalyDetector:
    def detect(self,s): return ["denied-access"] if not s.allowed else []
class RotationScheduler:
    def due(self,secrets_):
        now=datetime.now(timezone.utc); out=[]
        for s in secrets_:
            if s.rotation_interval_seconds and (s.last_rotated_at or s.created_at).timestamp()+s.rotation_interval_seconds<=now.timestamp(): out.append(s)
        return out
class IncidentResponse:
    def __init__(self,revoke_key:Callable[[str],None]): self.revoke_key=revoke_key
    def contain(self,key_id): self.revoke_key(key_id)
@dataclass(frozen=True,slots=True)
class AgentIdentity:
    agent_id:str; workload_id:str; environment:str; issued_at:datetime; expires_at:datetime
@dataclass(frozen=True,slots=True)
class CapabilityCredential:
    credential_id:str; agent_id:str; capability:str; scopes:frozenset[str]; issued_at:datetime; expires_at:datetime; ephemeral:bool=True
class AgentCredentialIssuer:
    def issue(self,identity,capability,scopes,ttl_seconds=300):
        if not 0<ttl_seconds<=3600: raise ValueError("agent credential TTL must be 1..3600 seconds")
        t=datetime.now(timezone.utc)
        return CapabilityCredential(secrets.token_urlsafe(18),identity.agent_id,capability,frozenset(scopes),t,t+timedelta(seconds=ttl_seconds))
class ApprovalGate:
    HIGH_RISK=frozenset({"production.write","secret.export","credential.rotate","infra.delete"})
    def requires_approval(self,capability): return capability in self.HIGH_RISK

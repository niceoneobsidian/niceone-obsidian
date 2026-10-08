"""Unified credential security control plane primitives.

This module supplies the durable domain contracts for secret lifecycle,
authorization, identity, capability, incident response, telemetry and evidence.
Provider-specific SDKs remain behind the provider abstraction.
"""
from __future__ import annotations
import hashlib, hmac, json, secrets, threading
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Callable, Iterable

class SecretState(StrEnum):
    ACTIVE="active"; ROTATING="rotating"; QUARANTINED="quarantined"; COMPROMISED="compromised"; REVOKED="revoked"; PURGED="purged"

class AccessDecision(StrEnum):
    ALLOW="allow"; DENY="deny"; APPROVAL_REQUIRED="approval_required"

@dataclass(frozen=True, slots=True)
class SecretVersion:
    version: str
    digest: str
    created_at: datetime
    state: SecretState = SecretState.ACTIVE
    activated_at: datetime | None = None
    revoked_at: datetime | None = None

@dataclass(frozen=True, slots=True)
class SecretRecord:
    id: str
    name: str
    provider: str
    environment: str
    owner_id: str
    service_id: str
    classification: str
    purpose: str
    state: SecretState = SecretState.ACTIVE
    versions: tuple[SecretVersion, ...] = ()
    workloads: frozenset[str] = frozenset()
    agents: frozenset[str] = frozenset()
    dependencies: frozenset[str] = frozenset()
    tags: tuple[tuple[str,str], ...] = ()

@dataclass(frozen=True, slots=True)
class PolicyRule:
    effect: AccessDecision
    subjects: frozenset[str] = frozenset()
    environments: frozenset[str] = frozenset()
    providers: frozenset[str] = frozenset()
    secrets: frozenset[str] = frozenset()
    scopes: frozenset[str] = frozenset()
    not_before: datetime | None = None
    not_after: datetime | None = None
    requires_approval: bool = False
    network: frozenset[str] = frozenset()

@dataclass(frozen=True, slots=True)
class AccessContext:
    subject_id: str
    environment: str
    scopes: frozenset[str] = frozenset()
    network: str | None = None
    trusted: bool = False
    device_id: str | None = None
    workload_id: str | None = None
    agent_id: str | None = None

class SecretControlPlane:
    """Thread-safe in-process reference control plane.

    The interface is deliberately provider-neutral so persistent implementations
    can be substituted without changing authorization or lifecycle contracts.
    """
    def __init__(self) -> None:
        self._lock=threading.RLock()
        self._secrets: dict[str, SecretRecord]={}
        self._values: dict[tuple[str,str],str]={}
        self._policies: list[PolicyRule]=[]
        self._events: list[dict[str,Any]]=[]
        self._quotas: dict[str, tuple[int,int]]={}
        self._usage: dict[str,list[datetime]]={}

    def register(self, record: SecretRecord) -> None:
        with self._lock:
            if record.id in self._secrets: raise ValueError(f"secret already exists: {record.id}")
            self._secrets[record.id]=record
            self._emit("secret.registered", record.id, record.owner_id)

    def get(self, secret_id: str) -> SecretRecord:
        with self._lock:
            return self._secrets[secret_id]

    def add_policy(self, rule: PolicyRule) -> None:
        with self._lock: self._policies.append(rule)

    def authorize(self, record: SecretRecord, context: AccessContext, *, scope: str|None=None, now: datetime|None=None) -> AccessDecision:
        now=now or datetime.now(UTC)
        matched=[r for r in self._policies if self._match(r,record,context,scope,now)]
        if any(r.effect is AccessDecision.DENY for r in matched): return AccessDecision.DENY
        if any(r.effect is AccessDecision.APPROVAL_REQUIRED or r.requires_approval for r in matched):
            return AccessDecision.APPROVAL_REQUIRED
        if matched: return AccessDecision.ALLOW
        return AccessDecision.DENY

    def _match(self,r:PolicyRule,s:SecretRecord,c:AccessContext,scope:str|None,now:datetime)->bool:
        return (
            (not r.subjects or c.subject_id in r.subjects)
            and (not r.environments or s.environment in r.environments)
            and (not r.providers or s.provider in r.providers)
            and (not r.secrets or s.id in r.secrets)
            and (not r.scopes or (scope is not None and scope in r.scopes))
            and (not r.network or c.network in r.network)
            and (r.not_before is None or now>=r.not_before)
            and (r.not_after is None or now<=r.not_after)
        )

    def put_version(self, secret_id:str, value:str, *, activate:bool=True) -> SecretVersion:
        with self._lock:
            record=self._secrets[secret_id]
            version=secrets.token_hex(12)
            digest=hashlib.sha256(value.encode()).hexdigest()
            state=SecretState.ACTIVE if activate else SecretState.ROTATING
            item=SecretVersion(version,digest,datetime.now(UTC),state,datetime.now(UTC) if activate else None)
            versions=list(record.versions)
            if activate:
                versions=[replace(v,state=SecretState.REVOKED,revoked_at=datetime.now(UTC)) if v.state is SecretState.ACTIVE else v for v in versions]
            versions.append(item)
            self._secrets[secret_id]=replace(record,versions=tuple(versions),state=SecretState.ACTIVE if activate else SecretState.ROTATING)
            self._values[(secret_id,version)]=value
            self._emit("secret.version.created",secret_id,"system",{"version":version})
            return item

    def resolve(self, secret_id:str, context:AccessContext, *, scope:str="read", now:datetime|None=None) -> str:
        with self._lock:
            record=self._secrets[secret_id]
            if record.state in {SecretState.REVOKED,SecretState.PURGED,SecretState.COMPROMISED,SecretState.QUARANTINED}:
                raise PermissionError(f"secret unavailable: {record.state}")
            if self.authorize(record,context,scope=scope,now=now) is not AccessDecision.ALLOW:
                self._emit("secret.access.denied",secret_id,context.subject_id); raise PermissionError("secret access denied")
            self._check_quota(context.subject_id,now or datetime.now(UTC))
            active=next((v for v in reversed(record.versions) if v.state is SecretState.ACTIVE),None)
            if active is None: raise RuntimeError("secret has no active version")
            self._usage.setdefault(secret_id,[]).append(now or datetime.now(UTC))
            self._emit("secret.accessed",secret_id,context.subject_id,{"version":active.version})
            return self._values[(secret_id,active.version)]

    def transition(self, secret_id:str, state:SecretState, actor:str) -> None:
        allowed={
            SecretState.ACTIVE:{SecretState.ROTATING,SecretState.QUARANTINED,SecretState.COMPROMISED,SecretState.REVOKED},
            SecretState.ROTATING:{SecretState.ACTIVE,SecretState.QUARANTINED,SecretState.COMPROMISED,SecretState.REVOKED},
            SecretState.QUARANTINED:{SecretState.ACTIVE,SecretState.COMPROMISED,SecretState.REVOKED},
            SecretState.COMPROMISED:{SecretState.ROTATING,SecretState.REVOKED},
            SecretState.REVOKED:{SecretState.PURGED},
            SecretState.PURGED:set(),
        }
        with self._lock:
            current=self._secrets[secret_id].state
            if state not in allowed[current]: raise ValueError(f"invalid state transition {current}->{state}")
            self._secrets[secret_id]=replace(self._secrets[secret_id],state=state)
            self._emit("secret.state.changed",secret_id,actor,{"from":current.value,"to":state.value})

    def quarantine(self,secret_id:str,actor:str)->None: self.transition(secret_id,SecretState.QUARANTINED,actor)
    def compromise(self,secret_id:str,actor:str)->None: self.transition(secret_id,SecretState.COMPROMISED,actor)

    def set_quota(self,subject_id:str,*,max_accesses:int,window_seconds:int)->None:
        self._quotas[subject_id]=(max_accesses,window_seconds)

    def _check_quota(self,subject_id:str,now:datetime)->None:
        quota=self._quotas.get(subject_id)
        if not quota:return
        limit,window=quota
        values=[x for x in self._usage.get(subject_id,[]) if (now-x).total_seconds()<=window]
        self._usage[subject_id]=values
        if len(values)>=limit: raise PermissionError("secret access quota exceeded")

    def _emit(self,event:str,resource_id:str,actor:str,metadata:dict[str,Any]|None=None)->None:
        self._events.append({"event":event,"resource_id":resource_id,"actor":actor,"occurred_at":datetime.now(UTC).isoformat(),"metadata":metadata or {}})

    def events(self)->tuple[dict[str,Any],...]:
        with self._lock:return tuple(self._events)

def constant_time_equal(left:str,right:str)->bool:
    return hmac.compare_digest(left.encode(),right.encode())

def score_secret_health(record:SecretRecord, *, now:datetime|None=None)->int:
    now=now or datetime.now(UTC); score=100
    if record.state is not SecretState.ACTIVE: score-=50
    if not record.versions: score-=35
    elif not any(v.state is SecretState.ACTIVE for v in record.versions): score-=35
    latest=max(record.versions,key=lambda v:v.created_at,default=None)
    if latest and (now-latest.created_at)>timedelta(days=90): score-=20
    if not record.owner_id or not record.service_id: score-=10
    return max(0,min(100,score))

"""P0/P1: taxonomy, metadata registry primitives, API keys and log redaction."""
from __future__ import annotations
import hashlib,hmac,os,re,secrets,sqlite3
from dataclasses import dataclass,field
from datetime import datetime,timedelta,timezone
from enum import StrEnum
from collections.abc import Iterable

class Environment(StrEnum): DEVELOPMENT="development"; TEST="test"; STAGING="staging"; PRODUCTION="production"
class SecretClassification(StrEnum): PUBLIC="public"; INTERNAL="internal"; SENSITIVE="sensitive"; SECRET="secret"; CRITICAL="critical"
class SecretStatus(StrEnum): ACTIVE="active"; ROTATING="rotating"; SUSPENDED="suspended"; REVOKED="revoked"; PURGED="purged"
def utcnow(): return datetime.now(timezone.utc)
@dataclass(frozen=True,slots=True)
class SecretMetadata:
    id:str; name:str; provider:str; environment:Environment; classification:SecretClassification
    owner_id:str; service_id:str; purpose:str; reference:str; status:SecretStatus=SecretStatus.ACTIVE
    created_at:datetime=field(default_factory=utcnow); last_rotated_at:datetime|None=None
    expires_at:datetime|None=None; rotation_interval_seconds:int|None=None; tags:dict[str,str]=field(default_factory=dict)
    def public_dict(self):
        return {"id":self.id,"name":self.name,"provider":self.provider,"environment":self.environment.value,
        "classification":self.classification.value,"owner_id":self.owner_id,"service_id":self.service_id,
        "purpose":self.purpose,"reference":self.reference,"status":self.status.value,
        "created_at":self.created_at.isoformat(),"last_rotated_at":self.last_rotated_at.isoformat() if self.last_rotated_at else None,
        "expires_at":self.expires_at.isoformat() if self.expires_at else None,
        "rotation_interval_seconds":self.rotation_interval_seconds,"tags":dict(self.tags)}
@dataclass(frozen=True,slots=True)
class ApiKeyRecord:
    id:str; key_prefix:str; key_hash:str; owner_id:str; project_id:str; service_id:str; environment:str
    name:str; scopes:frozenset[str]; status:str; created_at:datetime; expires_at:datetime|None
    last_used_at:datetime|None; rotated_at:datetime|None; revoked_at:datetime|None
def hash_api_key(raw: str, pepper: str | bytes | None = None) -> str:
    key = pepper if pepper is not None else os.getenv("OIS_API_KEY_PEPPER")
    if not key:
        raise RuntimeError("OIS_API_KEY_PEPPER is required for API-key hashing")
    key_bytes = key.encode() if isinstance(key, str) else key
    return hmac.new(key_bytes, raw.encode(), hashlib.sha256).hexdigest()
def generate_api_key(environment:str,prefix="odk",length=32)->str:
    if environment not in {x.value for x in Environment}: raise ValueError("unsupported environment")
    if length<32: raise ValueError("minimum entropy is 32 bytes")
    return f"{prefix}_{environment[:4]}_{secrets.token_urlsafe(length)}"
class ApiKeyManager:
    """Persistent metadata registry. Raw issued keys are never stored."""
    def __init__(self,database=":memory:"):
        self.db=sqlite3.connect(database); self.db.row_factory=sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS api_keys(id TEXT PRIMARY KEY,key_prefix TEXT,key_hash TEXT UNIQUE,
        owner_id TEXT,project_id TEXT,service_id TEXT,environment TEXT,name TEXT,scopes TEXT,status TEXT,created_at TEXT,
        expires_at TEXT,last_used_at TEXT,rotated_at TEXT,revoked_at TEXT)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS api_key_events(id INTEGER PRIMARY KEY AUTOINCREMENT,key_id TEXT,
        event TEXT,actor_id TEXT,occurred_at TEXT,metadata TEXT)"""); self.db.commit()
    def create(self,*,owner_id,project_id,service_id,environment,name,scopes:Iterable[str],expires_in:timedelta|None=None):
        raw=generate_api_key(environment); t=utcnow(); kid=secrets.token_hex(16); exp=t+expires_in if expires_in else None
        self.db.execute("INSERT INTO api_keys VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (kid,raw.rsplit("_",1)[0],hash_api_key(raw, self.pepper),owner_id,project_id,service_id,environment,name,
         ",".join(sorted(set(scopes))),"active",t.isoformat(),exp.isoformat() if exp else None,None,None,None))
        self._event(kid,"created",owner_id); self.db.commit(); return self.get(kid),raw
    def get(self,kid):
        row=self.db.execute("SELECT * FROM api_keys WHERE id=?",(kid,)).fetchone()
        if row is None: raise KeyError(kid)
        return self._record(row)
    def validate(self,raw,required_scope=None):
        digest=hash_api_key(raw, self.pepper); row=self.db.execute("SELECT * FROM api_keys WHERE key_hash=?",(digest,)).fetchone()
        if row is None or not hmac.compare_digest(row["key_hash"],digest): raise PermissionError("invalid API key")
        if row["status"]!="active": raise PermissionError("inactive API key")
        exp=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
        if exp and exp<=utcnow(): raise PermissionError("expired API key")
        scopes=frozenset(filter(None,row["scopes"].split(",")))
        if required_scope and required_scope not in scopes: raise PermissionError("insufficient scope")
        self.db.execute("UPDATE api_keys SET last_used_at=? WHERE id=?",(utcnow().isoformat(),row["id"]))
        self._event(row["id"],"validated","runtime"); self.db.commit(); return self.get(row["id"])
    def revoke(self,kid,actor_id):
        self.db.execute("UPDATE api_keys SET status='revoked',revoked_at=? WHERE id=?",(utcnow().isoformat(),kid))
        self._event(kid,"revoked",actor_id); self.db.commit()
    def rotate(self,kid,actor_id):
        old=self.get(kid); raw=generate_api_key(old.environment); t=utcnow(); new_id=secrets.token_hex(16)
        self.db.execute("UPDATE api_keys SET status='revoked',rotated_at=?,revoked_at=? WHERE id=?",(t.isoformat(),t.isoformat(),kid))
        self.db.execute("INSERT INTO api_keys VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (new_id,raw.rsplit("_",1)[0],hash_api_key(raw, self.pepper),old.owner_id,old.project_id,old.service_id,old.environment,old.name,
         ",".join(sorted(old.scopes)),"active",t.isoformat(),old.expires_at.isoformat() if old.expires_at else None,None,None,None))
        self._event(kid,"rotated",actor_id); self.db.commit(); return self.get(new_id),raw
    def _event(self,kid,event,actor):
        self.db.execute("INSERT INTO api_key_events(key_id,event,actor_id,occurred_at,metadata) VALUES(?,?,?,?,?)",
                        (kid,event,actor,utcnow().isoformat(),"{}"))
    @staticmethod
    def _record(r):
        return ApiKeyRecord(r["id"],r["key_prefix"],r["key_hash"],r["owner_id"],r["project_id"],r["service_id"],r["environment"],
        r["name"],frozenset(filter(None,r["scopes"].split(","))),r["status"],datetime.fromisoformat(r["created_at"]),
        datetime.fromisoformat(r["expires_at"]) if r["expires_at"] else None,datetime.fromisoformat(r["last_used_at"]) if r["last_used_at"] else None,
        datetime.fromisoformat(r["rotated_at"]) if r["rotated_at"] else None,datetime.fromisoformat(r["revoked_at"]) if r["revoked_at"] else None)
class SecretRedactor:
    def __init__(self,secrets=()): self._secrets=sorted({x for x in secrets if x},key=len,reverse=True)
    def add(self,value): self._secrets.append(value); self._secrets.sort(key=len,reverse=True)
    def redact(self,text):
        for value in self._secrets: text=text.replace(value,"[REDACTED]")
        text=re.sub(r"(?i)(api[_-]?key|token|secret|password|authorization)(\s*[=:]\s*)[^\s,;]+",r"\1\2[REDACTED]",text)
        return re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+","Bearer [REDACTED]",text)

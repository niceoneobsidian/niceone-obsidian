"""P0 metadata registry and P1/P4 audit log. Neither stores secret material."""
from __future__ import annotations
import json
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
from pathlib import Path
from .core import Environment,SecretClassification,SecretMetadata,SecretStatus

class SecretRegistry:
    def __init__(self,path=".ois/security/secrets/registry.json"): self.path=Path(path)
    def list(self):
        if not self.path.exists(): return []
        return [self._from_dict(x) for x in json.loads(self.path.read_text(encoding="utf-8"))]
    def upsert(self,metadata:SecretMetadata):
        records={x.id:x for x in self.list()}; records[metadata.id]=metadata
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.path.write_text(json.dumps([x.public_dict() for x in records.values()],indent=2)+"\n",encoding="utf-8")
        try:self.path.chmod(0o600)
        except OSError:pass
    @staticmethod
    def _from_dict(x):
        return SecretMetadata(id=x["id"],name=x["name"],provider=x["provider"],environment=Environment(x["environment"]),
        classification=SecretClassification(x["classification"]),owner_id=x["owner_id"],service_id=x["service_id"],
        purpose=x["purpose"],reference=x["reference"],status=SecretStatus(x["status"]),
        created_at=datetime.fromisoformat(x["created_at"]),
        last_rotated_at=datetime.fromisoformat(x["last_rotated_at"]) if x.get("last_rotated_at") else None,
        expires_at=datetime.fromisoformat(x["expires_at"]) if x.get("expires_at") else None,
        rotation_interval_seconds=x.get("rotation_interval_seconds"),tags=x.get("tags",{}))

@dataclass(frozen=True,slots=True)
class AuditEvent:
    event:str; actor_id:str; resource_id:str; occurred_at:str; metadata:dict
class SecurityAuditLog:
    def __init__(self,path=".ois/security/secrets/audit.jsonl"): self.path=Path(path)
    def record(self,event,actor_id,resource_id,metadata=None):
        item=AuditEvent(event,actor_id,resource_id,datetime.now(timezone.utc).isoformat(),metadata or {})
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open("a",encoding="utf-8") as h:h.write(json.dumps(asdict(item),sort_keys=True)+"\n")
        return item

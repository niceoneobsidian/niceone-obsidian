"""API-key issuance and lifecycle service."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hmac
import secrets
import sqlite3
from .core import hash_api_key

@dataclass(frozen=True, slots=True)
class ApiKeyView:
    id: str
    prefix: str
    owner_id: str
    project_id: str
    service_id: str
    environment: str
    name: str
    scopes: frozenset[str]
    status: str
    created_at: str
    expires_at: str | None
    last_used_at: str | None

class ApiKeyService:
    def __init__(self, database: str = ":memory:", pepper: str | bytes | None = None) -> None:
        self.pepper = pepper
        self.db = sqlite3.connect(database, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS keys(id TEXT PRIMARY KEY,prefix TEXT UNIQUE,hash TEXT UNIQUE,owner TEXT,project TEXT,service TEXT,environment TEXT,name TEXT,scopes TEXT,status TEXT,created TEXT,expires TEXT,last_used TEXT)")
        self.db.commit()

    def issue(self, *, owner_id: str, project_id: str, service_id: str, environment: str, name: str, scopes: set[str] | frozenset[str], expires_in: timedelta | None = None) -> tuple[ApiKeyView, str]:
        raw = f"ois_{environment[:4]}_{secrets.token_urlsafe(32)}"
        key_id = secrets.token_hex(16)
        now = datetime.now(UTC)
        expires = now + expires_in if expires_in else None
        self.db.execute("INSERT INTO keys VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (key_id, raw.rsplit("_", 1)[0], hash_api_key(raw, self.pepper), owner_id, project_id, service_id, environment, name, ",".join(sorted(scopes)), "active", now.isoformat(), expires.isoformat() if expires else None, None))
        self.db.commit()
        return self.view(key_id), raw

    def validate(self, raw: str, scope: str | None = None) -> ApiKeyView:
        digest = hash_api_key(raw, self.pepper)
        row = self.db.execute("SELECT * FROM keys WHERE hash=?", (digest,)).fetchone()
        if not row or not hmac.compare_digest(row[2], digest) or row[9] != "active":
            raise PermissionError("invalid API key")
        if row[11] and datetime.fromisoformat(row[11]) <= datetime.now(UTC):
            raise PermissionError("expired API key")
        scopes = set(filter(None, row[8].split(",")))
        if scope and scope not in scopes:
            raise PermissionError("insufficient scope")
        self.db.execute("UPDATE keys SET last_used=? WHERE id=?", (datetime.now(UTC).isoformat(), row[0]))
        self.db.commit()
        return self.view(row[0])

    def revoke(self, key_id: str) -> None:
        self.db.execute("UPDATE keys SET status='revoked' WHERE id=?", (key_id,))
        self.db.commit()

    def rotate(self, key_id: str) -> tuple[ApiKeyView, str]:
        old = self.view(key_id)
        self.revoke(key_id)
        return self.issue(owner_id=old.owner_id, project_id=old.project_id, service_id=old.service_id, environment=old.environment, name=old.name, scopes=old.scopes)

    def view(self, key_id: str) -> ApiKeyView:
        row = self.db.execute("SELECT * FROM keys WHERE id=?", (key_id,)).fetchone()
        if not row:
            raise KeyError(key_id)
        return ApiKeyView(row[0], row[1], row[3], row[4], row[5], row[6], row[7], frozenset(filter(None, row[8].split(","))), row[9], row[10], row[11], row[12])

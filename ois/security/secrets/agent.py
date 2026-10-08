"""Capability-based agent credential control."""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
import secrets

@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    risk: int
    scopes: frozenset[str]
    approval_required: bool = False

@dataclass(frozen=True, slots=True)
class AgentCredential:
    id: str
    agent_id: str
    capability: str
    scopes: frozenset[str]
    issued_at: datetime
    expires_at: datetime
    status: str = "active"
    parent_id: str | None = None
    provenance: tuple[str, ...] = ()

class AgentCapabilityGateway:
    def __init__(self) -> None:
        self.capabilities: dict[str, Capability] = {}
        self.credentials: dict[str, AgentCredential] = {}

    def register(self, capability: Capability) -> None:
        if not 0 <= capability.risk <= 100:
            raise ValueError("risk must be between 0 and 100")
        self.capabilities[capability.name] = capability

    def issue(self, agent_id: str, capability: str, *, scopes: frozenset[str], ttl: timedelta = timedelta(minutes=15), approved: bool = False, parent_id: str | None = None, delegation_depth: int = 0) -> AgentCredential:
        cap = self.capabilities[capability]
        if not scopes <= cap.scopes:
            raise PermissionError("capability scope denied")
        if (cap.risk >= 80 or cap.approval_required) and not approved:
            raise PermissionError("capability requires approval")
        if delegation_depth >= 3:
            raise PermissionError("delegation depth exceeded")
        now = datetime.now(UTC)
        credential = AgentCredential(secrets.token_hex(16), agent_id, capability, scopes, now, now + ttl, "active", parent_id, (parent_id,) if parent_id else ())
        self.credentials[credential.id] = credential
        return credential

    def validate(self, credential_id: str, scope: str | None = None) -> AgentCredential:
        credential = self.credentials[credential_id]
        if credential.status != "active" or credential.expires_at <= datetime.now(UTC):
            raise PermissionError("credential inactive or expired")
        if scope and scope not in credential.scopes:
            raise PermissionError("scope denied")
        return credential

    def revoke(self, credential_id: str) -> None:
        self.credentials[credential_id] = replace(self.credentials[credential_id], status="revoked")

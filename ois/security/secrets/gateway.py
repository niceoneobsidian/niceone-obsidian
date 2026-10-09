"""P5 agent capability gateway."""
from __future__ import annotations
from datetime import UTC, datetime
from typing import Any
from production.control_plane import AuthorizationPolicy, Subject

class AgentCapabilityGateway:
    def __init__(self, issuer: Any, approval_gate: Any, authorization: Any, audit: Any = None) -> None:
        self.issuer, self.approval_gate, self.authorization, self.audit = issuer, approval_gate, authorization, audit
    def issue(self, identity: Any, capability: str, scopes: set[str] | frozenset[str], *, approved: bool = False, ttl_seconds: int = 300, tenant_id: str = "default", permissions: frozenset[str] = frozenset()):
        if self.approval_gate.requires_approval(capability) and not approved:
            if self.audit: self.audit.record("agent.capability.denied", identity.agent_id, capability)
            raise PermissionError("high-risk capability requires approval")
        if self.authorization is not None:
            self.authorization.authorize(Subject(subject_id=identity.agent_id, tenant_id=tenant_id, permissions=permissions), AuthorizationPolicy(permission=capability))
        credential = self.issuer.issue(identity, capability, scopes, ttl_seconds=ttl_seconds)
        if self.audit: self.audit.record("agent.capability.issued", identity.agent_id, credential.credential_id)
        return credential
    def authorize(self, credential: Any, identity: Any, capability: str, required_scope: str | None = None) -> bool:
        if credential.agent_id != identity.agent_id or credential.expires_at <= datetime.now(UTC) or credential.capability != capability:
            raise PermissionError("invalid or expired agent capability credential")
        if required_scope and required_scope not in credential.scopes:
            raise PermissionError("capability scope missing")
        if self.audit: self.audit.record("agent.capability.authorized", identity.agent_id, credential.credential_id)
        return True

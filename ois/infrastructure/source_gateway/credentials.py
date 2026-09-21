"""Credential references and tenant isolation for source integrations.

Secrets are never stored in domain records. A credential reference identifies
an external secret managed by deployment infrastructure; the resolver is the
only component allowed to materialize the secret for a request.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TenantScope:
    tenant_id: str
    workspace_id: str

    def assert_matches(self, tenant_id: str, workspace_id: str) -> None:
        if self.tenant_id != tenant_id or self.workspace_id != workspace_id:
            raise PermissionError("source request is outside its tenant/workspace scope")


@dataclass(frozen=True)
class CredentialRef:
    credential_id: str
    tenant_id: str
    provider: str
    scopes: tuple[str, ...] = ()


class CredentialResolver(Protocol):
    def resolve(self, ref: CredentialRef, scope: TenantScope) -> str: ...


class InMemoryCredentialResolver:
    """Test/development resolver; production should bind to a secret manager."""

    def __init__(self, credentials: dict[str, str] | None = None) -> None:
        self._credentials = dict(credentials or {})

    def resolve(self, ref: CredentialRef, scope: TenantScope) -> str:
        if ref.tenant_id != scope.tenant_id:
            raise PermissionError("credential belongs to another tenant")
        try:
            return self._credentials[ref.credential_id]
        except KeyError as exc:
            raise KeyError(f"credential not configured: {ref.credential_id}") from exc

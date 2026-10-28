"""Credential references and tenant isolation for source integrations.

Secrets are never stored in domain records. A credential reference identifies
an external secret managed by deployment infrastructure; the resolver is the
only component allowed to materialize the secret for a request.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
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
    expires_at: datetime | None = None


class CredentialResolver(Protocol):
    def resolve(self, ref: CredentialRef, scope: TenantScope) -> str: ...


class InMemoryCredentialResolver:
    """Test/development resolver; production should bind to a secret manager.

    ``owners`` optionally binds a credential id to the tenant that owns it. With
    ``strict_ownership`` a credential that has no owner is refused, so a tenant
    cannot read another tenant's secret by forging ``CredentialRef.tenant_id``.
    Without ``owners`` the legacy behaviour is kept and is NOT tenant-isolating.
    """

    def __init__(
        self,
        credentials: dict[str, str] | None = None,
        *,
        owners: Mapping[str, str] | None = None,
        strict_ownership: bool = False,
    ) -> None:
        self._credentials = dict(credentials or {})
        self._owners = dict(owners or {})
        self._strict = strict_ownership

    def resolve(self, ref: CredentialRef, scope: TenantScope) -> str:
        if ref.tenant_id != scope.tenant_id:
            raise PermissionError("credential belongs to another tenant")
        owner = self._owners.get(ref.credential_id)
        if owner is None and self._strict:
            raise PermissionError("credential has no tenant owner")
        if owner is not None and owner != scope.tenant_id:
            raise PermissionError("credential belongs to another tenant")
        try:
            return self._credentials[ref.credential_id]
        except KeyError as exc:
            raise KeyError(f"credential not configured: {ref.credential_id}") from exc

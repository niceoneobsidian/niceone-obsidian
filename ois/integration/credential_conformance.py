"""CredentialResolver conformance contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ois.infrastructure.source_gateway.credentials import (
    CredentialRef,
    TenantScope,
)
from ois.infrastructure.source_gateway.credentials import (
    CredentialResolver as ScopedCredentialResolver,
)


class CredentialResolver(Protocol):
    def resolve(self, *, tenant_id: str, workspace_id: str, credential_id: str) -> object: ...


@dataclass(frozen=True)
class CredentialResolutionProof:
    tenant_id: str
    workspace_id: str
    credential_id: str
    resolved: bool
    cross_tenant_blocked: bool
    evidence: tuple[str, ...] = ()


def assert_credential_resolver_conformance(
    resolver: CredentialResolver,
) -> CredentialResolutionProof:
    good = resolver.resolve(
        tenant_id="tenant-a", workspace_id="workspace-a", credential_id="cred-a"
    )
    if good is None:
        raise AssertionError("resolver failed valid credential resolution")
    blocked = False
    try:
        resolver.resolve(tenant_id="tenant-b", workspace_id="workspace-a", credential_id="cred-a")
    except (PermissionError, KeyError, ValueError):
        blocked = True
    if not blocked:
        raise AssertionError("credential resolver permitted cross-tenant credential access")
    return CredentialResolutionProof(
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        credential_id="cred-a",
        resolved=True,
        cross_tenant_blocked=True,
        evidence=("valid-resolution", "cross-tenant-denial"),
    )


def assert_scoped_resolver_conformance(
    resolver: ScopedCredentialResolver,
    *,
    owner_tenant: str,
    other_tenant: str,
    workspace_id: str,
    credential_id: str,
    provider: str,
) -> CredentialResolutionProof:
    """Check the real ``resolve(ref, scope)`` contract, including forged-ref attacks."""
    own_ref = CredentialRef(credential_id, owner_tenant, provider)
    secret = resolver.resolve(own_ref, TenantScope(owner_tenant, workspace_id))
    if not isinstance(secret, str) or not secret:
        raise AssertionError("resolver failed valid credential resolution")
    attacks = (
        # Attacker tenant forges a ref that claims its own tenant for the owner's credential id.
        (
            CredentialRef(credential_id, other_tenant, provider),
            TenantScope(other_tenant, workspace_id),
        ),
        # Owner's ref presented under another tenant's scope.
        (own_ref, TenantScope(other_tenant, workspace_id)),
    )
    for ref, scope in attacks:
        try:
            resolver.resolve(ref, scope)
        except (PermissionError, KeyError, ValueError):
            continue
        raise AssertionError("credential resolver permitted cross-tenant credential access")
    return CredentialResolutionProof(
        tenant_id=owner_tenant,
        workspace_id=workspace_id,
        credential_id=credential_id,
        resolved=True,
        cross_tenant_blocked=True,
        evidence=("valid-resolution", "forged-ref-denial", "scope-mismatch-denial"),
    )

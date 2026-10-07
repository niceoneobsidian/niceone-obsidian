"""CredentialResolver conformance contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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

"""Central credential and authentication orchestration.

Provider connectors declare *what* authentication they need. This manager owns
credential resolution, tenant/workspace authorization, and application of the
selected authentication scheme. Secret material never leaves this boundary
except as request headers/signatures produced by an authenticator.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from .auth import (
    Authenticator,
    AuthRequest,
    AuthScheme,
    CredentialMaterial,
    authenticator_for,
)
from .credentials import CredentialRef, CredentialResolver, TenantScope


@dataclass(frozen=True)
class AuthPolicy:
    """Declarative authentication requirements for a provider connector."""

    scheme: AuthScheme
    options: dict[str, object] | None = None


class CredentialAuthManager:
    """Resolve scoped credentials and apply a governed authentication policy."""

    def __init__(self, resolver: CredentialResolver) -> None:
        self._resolver = resolver

    def resolve(
        self,
        ref: CredentialRef,
        scope: TenantScope,
        *,
        client_id: str | None = None,
        token_type: str = "Bearer",
        required_scopes: Iterable[str] = (),
        expected_provider: str | None = None,
        now: datetime | None = None,
    ) -> CredentialMaterial:
        if ref.tenant_id != scope.tenant_id:
            raise PermissionError("credential belongs to another tenant")
        if expected_provider is not None and ref.provider != expected_provider:
            raise PermissionError("credential belongs to another provider")
        if ref.expires_at is not None:
            if ref.expires_at.tzinfo is None:
                raise PermissionError("credential expiry must be timezone-aware")
            if (now or datetime.now(UTC)) >= ref.expires_at:
                raise PermissionError("credential has expired")
        missing = set(required_scopes) - set(ref.scopes)
        if missing:
            raise PermissionError("credential lacks required scopes: " + ", ".join(sorted(missing)))
        secret = self._resolver.resolve(ref, scope)
        if not secret:
            raise PermissionError("credential material is empty")
        return CredentialMaterial(
            secret=secret,
            client_id=client_id,
            token_type=token_type,
        )

    def authenticate(
        self,
        request: AuthRequest,
        ref: CredentialRef,
        scope: TenantScope,
        policy: AuthPolicy,
        *,
        client_id: str | None = None,
        token_type: str = "Bearer",
        authenticator: Authenticator | None = None,
    ) -> AuthRequest:
        if authenticator is None and policy.scheme is AuthScheme.NONE:
            return request
        if ref.tenant_id != scope.tenant_id:
            raise PermissionError("credential belongs to another tenant")
        if not ref.provider:
            raise ValueError("credential provider is required")
        material = self.resolve(
            ref,
            scope,
            client_id=client_id,
            token_type=token_type,
        )
        auth = authenticator or authenticator_for(
            policy.scheme,
            **(policy.options or {}),
        )
        return auth.apply(request, material)

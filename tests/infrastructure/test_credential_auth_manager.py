from __future__ import annotations

import pytest

from ois.infrastructure.source_gateway.auth import (
    AuthRequest,
    AuthScheme,
    CredentialMaterial,
)
from ois.infrastructure.source_gateway.credentials import (
    CredentialRef,
    InMemoryCredentialResolver,
    TenantScope,
)
from ois.infrastructure.source_gateway.manager import AuthPolicy, CredentialAuthManager


def test_manager_resolves_and_applies_api_key_without_exposing_storage() -> None:
    manager = CredentialAuthManager(InMemoryCredentialResolver({"c1": "secret-key"}))
    result = manager.authenticate(
        AuthRequest("GET", "https://example.test", {}),
        CredentialRef("c1", "tenant-a", "example"),
        TenantScope("tenant-a", "workspace-a"),
        AuthPolicy(AuthScheme.API_KEY, {"header": "X-Client-Key"}),
    )
    assert result.headers["X-Client-Key"] == "secret-key"


def test_manager_rejects_cross_tenant_credentials() -> None:
    manager = CredentialAuthManager(InMemoryCredentialResolver({"c1": "secret-key"}))
    with pytest.raises(PermissionError):
        manager.authenticate(
            AuthRequest("GET", "https://example.test", {}),
            CredentialRef("c1", "tenant-b", "example"),
            TenantScope("tenant-a", "workspace-a"),
            AuthPolicy(AuthScheme.BEARER),
        )


def test_manager_rejects_empty_secret() -> None:
    manager = CredentialAuthManager(InMemoryCredentialResolver({"c1": ""}))
    with pytest.raises(PermissionError, match="empty"):
        manager.resolve(
            CredentialRef("c1", "tenant-a", "example"),
            TenantScope("tenant-a", "workspace-a"),
        )


def test_manager_supports_oauth_client_material() -> None:
    manager = CredentialAuthManager(InMemoryCredentialResolver({"c1": "client-secret"}))
    result = manager.authenticate(
        AuthRequest("POST", "https://example.test/token", {}),
        CredentialRef("c1", "tenant-a", "google"),
        TenantScope("tenant-a", "workspace-a"),
        AuthPolicy(AuthScheme.OAUTH2),
        client_id="client-id",
        authenticator=None,
    )
    assert result.headers["Authorization"].startswith("Bearer ")


def test_manager_applies_explicit_provider_authenticator() -> None:
    class CustomAuthenticator:
        scheme = AuthScheme.NONE

        def apply(self, request: AuthRequest, credential: CredentialMaterial) -> AuthRequest:
            headers = dict(request.headers)
            headers["X-Custom-Signature"] = f"sig:{credential.secret}"
            return AuthRequest(request.method, request.url, headers, request.body)

    manager = CredentialAuthManager(InMemoryCredentialResolver({"c1": "provider-secret"}))
    result = manager.authenticate(
        AuthRequest("GET", "https://example.test", {}),
        CredentialRef("c1", "tenant-a", "provider"),
        TenantScope("tenant-a", "workspace-a"),
        AuthPolicy(AuthScheme.NONE),
        authenticator=CustomAuthenticator(),
    )

    assert result.headers["X-Custom-Signature"] == "sig:provider-secret"


def test_manager_returns_unauthenticated_request_for_none_policy() -> None:
    manager = CredentialAuthManager(InMemoryCredentialResolver())
    request = AuthRequest("GET", "https://example.test", {"X-Test": "1"})
    assert (
        manager.authenticate(
            request,
            CredentialRef("unused", "tenant-a", "example"),
            TenantScope("tenant-a", "workspace-a"),
            AuthPolicy(AuthScheme.NONE),
        )
        == request
    )

from __future__ import annotations

from ois.infrastructure.source_gateway import (
    CredentialRef,
    InMemoryCredentialResolver,
    SourceGateway,
    TenantScope,
)
from ois.infrastructure.source_gateway.auth import AuthRequest, AuthScheme


def test_gateway_authentication_uses_central_manager() -> None:
    gateway = SourceGateway(credentials=InMemoryCredentialResolver({"cred": "token-123"}))
    result = gateway.authenticate_request(
        AuthRequest("GET", "https://example.test", {}),
        CredentialRef("cred", "tenant-a", "google"),
        TenantScope("tenant-a", "workspace-a"),
        AuthScheme.BEARER,
    )
    assert result.headers["Authorization"] == "Bearer token-123"

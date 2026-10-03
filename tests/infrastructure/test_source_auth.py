from __future__ import annotations

import base64
import re

from ois.infrastructure.source_gateway.auth import (
    ApiKeyAuth,
    AuthRequest,
    BearerAuth,
    CredentialMaterial,
    HmacAuth,
    OAuth2Auth,
)


def request() -> AuthRequest:
    return AuthRequest("POST", "https://example.test/v1/items?x=1", {}, b'{"id":1}')


def test_api_key_auth_is_declarative() -> None:
    result = ApiKeyAuth(header="X-Client-Key").apply(
        request(), CredentialMaterial("key-123")
    )
    assert result.headers["X-Client-Key"] == "key-123"


def test_bearer_auth_adds_authorization_header() -> None:
    result = BearerAuth().apply(request(), CredentialMaterial("token-123"))
    assert result.headers["Authorization"] == "Bearer token-123"


def test_oauth2_uses_current_access_token_without_token_logic() -> None:
    result = OAuth2Auth().apply(request(), CredentialMaterial("access-123"))
    assert result.headers["Authorization"] == "Bearer access-123"


def test_hmac_auth_signs_canonical_request() -> None:
    result = HmacAuth().apply(request(), CredentialMaterial("secret-123"))
    assert result.headers["X-Timestamp"]
    assert re.fullmatch(r"[0-9a-f]{64}", result.headers["X-Signature"])


def test_oauth_client_material_can_use_basic_auth() -> None:
    from ois.infrastructure.source_gateway.auth import BasicClientAuth

    result = BasicClientAuth().apply(
        request(), CredentialMaterial("client-secret", client_id="client-id")
    )
    expected = base64.b64encode(b"client-id:client-secret").decode("ascii")
    assert result.headers["Authorization"] == f"Basic {expected}"

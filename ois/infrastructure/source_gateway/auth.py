"""Formal authentication strategies for governed source connectors.

Generic adapters consume these policies; provider-specific connectors should only
declare the policy and credential reference they require.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlsplit


class AuthScheme(StrEnum):
    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"
    OAUTH2 = "oauth2"
    HMAC = "hmac"


@dataclass(frozen=True)
class AuthRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes = b""


@dataclass(frozen=True)
class CredentialMaterial:
    secret: str
    client_id: str | None = None
    token_type: str = "Bearer"


class Authenticator(Protocol):
    @property
    def scheme(self) -> AuthScheme: ...

    def apply(self, request: AuthRequest, credential: CredentialMaterial) -> AuthRequest: ...


@dataclass(frozen=True)
class ApiKeyAuth:
    """Attach a static API key to a request header."""

    header: str = "X-API-Key"
    scheme: AuthScheme = AuthScheme.API_KEY

    def apply(self, request: AuthRequest, credential: CredentialMaterial) -> AuthRequest:
        headers = dict(request.headers)
        headers[self.header] = credential.secret
        return AuthRequest(request.method, request.url, headers, request.body)


@dataclass(frozen=True)
class BearerAuth:
    """Attach an access token as an Authorization bearer token."""

    scheme: AuthScheme = AuthScheme.BEARER

    def apply(self, request: AuthRequest, credential: CredentialMaterial) -> AuthRequest:
        headers = dict(request.headers)
        headers["Authorization"] = f"{credential.token_type} {credential.secret}"
        return AuthRequest(request.method, request.url, headers, request.body)


@dataclass(frozen=True)
class OAuth2Auth(BearerAuth):
    """OAuth2 access-token transport.

    Token exchange and refresh belong to an OAuth2 token provider, not the
    generic HTTP adapter. The credential material supplied here is the current
    access token.
    """

    scheme: AuthScheme = AuthScheme.OAUTH2


@dataclass(frozen=True)
class HmacAuth:
    """Sign the HTTP request with an HMAC secret.

    The canonical form is intentionally deterministic so providers can opt into
    a standard signer without putting cryptographic logic in adapters.
    """

    signature_header: str = "X-Signature"
    timestamp_header: str = "X-Timestamp"
    algorithm: str = "sha256"
    prefix: str = ""
    scheme: AuthScheme = AuthScheme.HMAC

    def apply(self, request: AuthRequest, credential: CredentialMaterial) -> AuthRequest:
        if self.algorithm != "sha256":
            raise ValueError(f"unsupported HMAC algorithm: {self.algorithm}")

        timestamp = datetime.now(UTC).isoformat()
        parsed = urlsplit(request.url)
        canonical = "\n".join(
            (
                request.method.upper(),
                parsed.path or "/",
                parsed.query,
                timestamp,
                hashlib.sha256(request.body).hexdigest(),
            )
        ).encode("utf-8")
        digest = hmac.new(
            credential.secret.encode("utf-8"),
            canonical,
            hashlib.sha256,
        ).hexdigest()
        headers = dict(request.headers)
        headers[self.timestamp_header] = timestamp
        headers[self.signature_header] = f"{self.prefix}{digest}"
        return AuthRequest(request.method, request.url, headers, request.body)


@dataclass(frozen=True)
class BasicClientAuth:
    """Optional client-id/secret material for OAuth token endpoints."""

    scheme: AuthScheme = AuthScheme.OAUTH2

    def apply(self, request: AuthRequest, credential: CredentialMaterial) -> AuthRequest:
        if not credential.client_id:
            raise ValueError("OAuth client authentication requires client_id")
        encoded = base64.b64encode(f"{credential.client_id}:{credential.secret}".encode()).decode(
            "ascii"
        )
        headers = dict(request.headers)
        headers["Authorization"] = f"Basic {encoded}"
        return AuthRequest(request.method, request.url, headers, request.body)


def authenticator_for(scheme: AuthScheme, **kwargs: object) -> Authenticator:
    """Build a governed authenticator from declarative connector configuration."""
    if scheme is AuthScheme.NONE:
        raise ValueError("none authentication does not require an authenticator")
    if scheme is AuthScheme.API_KEY:
        return ApiKeyAuth(header=str(kwargs.get("header", "X-API-Key")))
    if scheme is AuthScheme.BEARER:
        return BearerAuth()
    if scheme is AuthScheme.OAUTH2:
        return OAuth2Auth()
    if scheme is AuthScheme.HMAC:
        return HmacAuth(
            signature_header=str(kwargs.get("signature_header", "X-Signature")),
            timestamp_header=str(kwargs.get("timestamp_header", "X-Timestamp")),
            algorithm=str(kwargs.get("algorithm", "sha256")),
            prefix=str(kwargs.get("prefix", "")),
        )
    raise ValueError(f"unsupported authentication scheme: {scheme}")

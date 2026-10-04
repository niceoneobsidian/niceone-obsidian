"""Reusable OAuth2 provider and secret-store boundaries."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Protocol

from ois.infrastructure.oauth2 import OAuth2Provider
from ois.infrastructure.oauth2_connection import (
    OAuthCredentialRecord,
    OAuthCredentialStore,
)
from ois.infrastructure.source_gateway.credentials import CredentialRef, TenantScope


class OAuthSecretBackend(Protocol):
    """Encrypted secret-manager boundary.

    The backend owns encryption, access control, audit logging, rotation, and
    durable storage. OIS only passes structured credential material to it.
    """

    def read(self, key: str) -> dict[str, object] | None: ...

    def write(self, key: str, value: dict[str, object]) -> None: ...


class SecretManagerOAuthCredentialStore(OAuthCredentialStore):
    """OAuthCredentialStore backed by an encrypted deployment secret manager."""

    def __init__(self, backend: OAuthSecretBackend, *, key_prefix: str = "ois/oauth") -> None:
        if not key_prefix or key_prefix.endswith("/"):
            raise ValueError("key_prefix must be non-empty and must not end with '/'")
        self._backend = backend
        self._key_prefix = key_prefix

    def save(self, record: OAuthCredentialRecord) -> None:
        self._backend.write(self._key(record.credential_id), _serialize(record))

    def get(
        self,
        credential_id: str,
        *,
        tenant_id: str,
        workspace_id: str,
        provider: str,
    ) -> OAuthCredentialRecord:
        payload = self._backend.read(self._key(credential_id))
        if payload is None:
            raise KeyError(f"OAuth credential not found: {credential_id}")
        record = _deserialize(payload)
        if (
            record.credential_id != credential_id
            or record.tenant_id != tenant_id
            or record.workspace_id != workspace_id
            or not (provider == record.provider or provider.startswith(f"{record.provider}."))
        ):
            raise PermissionError("OAuth credential is outside its tenant/workspace/provider scope")
        return record

    def resolve(self, ref: CredentialRef, scope: TenantScope) -> str:
        return self.get(
            ref.credential_id,
            tenant_id=scope.tenant_id,
            workspace_id=scope.workspace_id,
            provider=ref.provider,
        ).access_token

    def _key(self, credential_id: str) -> str:
        if not credential_id or "/" in credential_id:
            raise ValueError("credential_id must be non-empty and path-safe")
        return f"{self._key_prefix}/{credential_id}"


class OAuth2ProviderRegistry:
    """Explicit registry for provider-neutral OAuth2 providers."""

    def __init__(self, providers: dict[str, OAuth2Provider] | None = None) -> None:
        self._providers: dict[str, OAuth2Provider] = {}
        for provider in (providers or {}).values():
            self.register(provider)

    def register(self, provider: OAuth2Provider) -> None:
        name = provider.config.provider
        if name in self._providers:
            raise ValueError(f"OAuth2 provider already registered: {name}")
        self._providers[name] = provider

    def get(self, provider: str) -> OAuth2Provider:
        try:
            return self._providers[provider]
        except KeyError as exc:
            raise KeyError(f"OAuth2 provider not registered: {provider}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))


def _serialize(record: OAuthCredentialRecord) -> dict[str, object]:
    value = asdict(record)
    value["obtained_at"] = record.obtained_at.isoformat() if record.obtained_at else None
    value["expires_at"] = record.expires_at.isoformat() if record.expires_at else None
    value["scopes"] = list(record.scopes)
    return value


def _deserialize(payload: dict[str, object]) -> OAuthCredentialRecord:
    required = (
        "credential_id",
        "tenant_id",
        "workspace_id",
        "provider",
        "access_token",
        "token_type",
        "scopes",
    )
    if any(not payload.get(key) for key in required):
        raise ValueError("OAuth secret backend returned an incomplete credential record")

    scopes = payload["scopes"]
    if not isinstance(scopes, list) or not all(isinstance(scope, str) for scope in scopes):
        raise ValueError("OAuth secret backend returned invalid scopes")

    obtained_at = payload.get("obtained_at")
    expires_at = payload.get("expires_at")
    return OAuthCredentialRecord(
        credential_id=str(payload["credential_id"]),
        tenant_id=str(payload["tenant_id"]),
        workspace_id=str(payload["workspace_id"]),
        provider=str(payload["provider"]),
        access_token=str(payload["access_token"]),
        refresh_token=str(payload["refresh_token"]) if payload.get("refresh_token") else None,
        token_type=str(payload["token_type"]),
        scopes=tuple(scopes),
        obtained_at=datetime.fromisoformat(str(obtained_at)) if obtained_at else None,
        expires_at=datetime.fromisoformat(str(expires_at)) if expires_at else None,
    )

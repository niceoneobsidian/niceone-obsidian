"""OAuth-to-source connection orchestration.

The application service binds OAuth authorization to tenant/workspace-scoped
credentials and the governed source socket. Production deployments should
provide a durable, encrypted credential store and a shared state store.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from ois.infrastructure.oauth2 import OAuth2Provider, OAuth2Token
from ois.infrastructure.source_adapters.base import AdapterResult
from ois.infrastructure.source_gateway.credentials import (
    CredentialRef,
    CredentialResolver,
    TenantScope,
)
from ois.infrastructure.source_gateway.socket import ApiSourceSocket


@dataclass(frozen=True)
class OAuthCredentialRecord:
    credential_id: str
    tenant_id: str
    workspace_id: str
    provider: str
    access_token: str
    refresh_token: str | None
    token_type: str
    scopes: tuple[str, ...]
    obtained_at: datetime | None
    expires_at: datetime | None

    def ref(self) -> CredentialRef:
        return CredentialRef(
            credential_id=self.credential_id,
            tenant_id=self.tenant_id,
            provider=self.provider,
            scopes=self.scopes,
        )

    def is_expired(self, *, skew_seconds: int = 60) -> bool:
        if self.expires_at is None:
            return False
        return self.expires_at <= datetime.now(UTC) + timedelta(seconds=skew_seconds)


class OAuthCredentialStore(CredentialResolver, Protocol):
    """Durable secret boundary for OAuth credentials.

    Implementations must encrypt token material at rest and enforce the
    tenant/workspace/provider scope on every read and write.
    """

    def save(self, record: OAuthCredentialRecord) -> None: ...

    def get(
        self,
        credential_id: str,
        *,
        tenant_id: str,
        workspace_id: str,
        provider: str,
    ) -> OAuthCredentialRecord: ...


class InMemoryOAuthCredentialStore:
    """Development/test credential store; never use as a production secret store."""

    def __init__(self) -> None:
        self._records: dict[str, OAuthCredentialRecord] = {}

    def save(self, record: OAuthCredentialRecord) -> None:
        self._records[record.credential_id] = record

    def get(
        self,
        credential_id: str,
        *,
        tenant_id: str,
        workspace_id: str,
        provider: str,
    ) -> OAuthCredentialRecord:
        record = self._records.get(credential_id)
        if record is None:
            raise KeyError(f"OAuth credential not found: {credential_id}")
        if (
            record.tenant_id != tenant_id
            or record.workspace_id != workspace_id
            or not (provider == record.provider or provider.startswith(f"{record.provider}."))
        ):
            raise PermissionError("OAuth credential is outside its tenant/workspace/provider scope")
        return record

    def resolve(
        self,
        ref: CredentialRef,
        scope: TenantScope,
    ) -> str:
        return self.get(
            ref.credential_id,
            tenant_id=scope.tenant_id,
            workspace_id=scope.workspace_id,
            provider=ref.provider,
        ).access_token


class OAuth2SourceConnection:
    """Application service for an authenticated live-source connection."""

    def __init__(
        self,
        *,
        providers: dict[str, OAuth2Provider],
        credentials: OAuthCredentialStore,
        socket: ApiSourceSocket,
        refresh_skew_seconds: int = 60,
    ) -> None:
        if refresh_skew_seconds < 0:
            raise ValueError("refresh_skew_seconds cannot be negative")
        self._providers = dict(providers)
        self._credentials = credentials
        self._socket = socket
        self._refresh_skew_seconds = refresh_skew_seconds

    def begin(
        self,
        *,
        provider: str,
        tenant_id: str,
        workspace_id: str,
    ) -> tuple[str, str]:
        return self._provider(provider).authorization_url(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )

    def complete(
        self,
        *,
        provider: str,
        tenant_id: str,
        workspace_id: str,
        state: str,
        code: str,
        credential_id: str,
    ) -> CredentialRef:
        if not credential_id:
            raise ValueError("credential_id is required")
        oauth = self._provider(provider)
        oauth.validate_state(
            state,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        token = oauth.exchange_code(code)
        record = self._record(
            credential_id=credential_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            provider=provider,
            token=token,
        )
        self._credentials.save(record)
        return record.ref()

    def refresh(
        self,
        *,
        provider: str,
        tenant_id: str,
        workspace_id: str,
        credential_id: str,
    ) -> CredentialRef:
        current = self._credentials.get(
            credential_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            provider=provider,
        )
        updated = self._refresh_record(current)
        return updated.ref()

    def ingest(
        self,
        *,
        provider: str,
        source_id: str,
        tenant_id: str,
        workspace_id: str,
        credential_id: str,
    ) -> AdapterResult:
        current = self._credentials.get(
            credential_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            provider=provider,
        )
        if current.is_expired(skew_seconds=self._refresh_skew_seconds):
            current = self._refresh_record(current)
        return self._socket.ingest(
            source_id,
            tenant_id=current.tenant_id,
            workspace_id=current.workspace_id,
            credential_id=current.credential_id,
        )

    def _refresh_record(self, current: OAuthCredentialRecord) -> OAuthCredentialRecord:
        if not current.refresh_token:
            raise ValueError("OAuth credential has no refresh token")
        token = self._provider(current.provider).refresh(current.refresh_token)
        updated = self._record(
            credential_id=current.credential_id,
            tenant_id=current.tenant_id,
            workspace_id=current.workspace_id,
            provider=current.provider,
            token=token,
            fallback_scopes=current.scopes,
            fallback_refresh_token=current.refresh_token,
        )
        self._credentials.save(updated)
        return updated

    def _provider(self, provider: str) -> OAuth2Provider:
        try:
            return self._providers[provider]
        except KeyError as exc:
            raise KeyError(f"OAuth provider not configured: {provider}") from exc

    @staticmethod
    def _record(
        *,
        credential_id: str,
        tenant_id: str,
        workspace_id: str,
        provider: str,
        token: OAuth2Token,
        fallback_scopes: tuple[str, ...] = (),
        fallback_refresh_token: str | None = None,
    ) -> OAuthCredentialRecord:
        return OAuthCredentialRecord(
            credential_id=credential_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            provider=provider,
            access_token=token.access_token,
            refresh_token=token.refresh_token or fallback_refresh_token,
            token_type=token.token_type,
            scopes=token.scope or fallback_scopes,
            obtained_at=token.obtained_at,
            expires_at=token.expires_at,
        )

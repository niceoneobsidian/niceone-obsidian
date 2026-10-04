from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from ois.infrastructure.oauth2 import OAuth2Token
from ois.infrastructure.oauth2_connection import (
    InMemoryOAuthCredentialStore,
    OAuth2SourceConnection,
    OAuthCredentialRecord,
)
from ois.infrastructure.oauth2_registry import (
    OAuth2ProviderRegistry,
    SecretManagerOAuthCredentialStore,
)
from ois.integrations.github import build_github_oauth


class MemorySecrets:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, object]] = {}

    def read(self, key: str) -> dict[str, object] | None:
        return self.values.get(key)

    def write(self, key: str, value: dict[str, object]) -> None:
        self.values[key] = value


def test_secret_manager_store_round_trips_and_enforces_scope() -> None:
    backend = MemorySecrets()
    store = SecretManagerOAuthCredentialStore(backend)
    record = OAuthCredentialRecord(
        credential_id="cred-1",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        provider="github",
        access_token="secret-access",
        refresh_token="secret-refresh",
        token_type="Bearer",
        scopes=("read:user",),
        obtained_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    store.save(record)
    assert (
        store.get(
            "cred-1",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            provider="github.rest.user",
        )
        == record
    )
    with pytest.raises(PermissionError):
        store.get(
            "cred-1",
            tenant_id="tenant-2",
            workspace_id="workspace-1",
            provider="github",
        )
    assert backend.values["ois/oauth/cred-1"]["access_token"] == "secret-access"


def test_secret_manager_store_rejects_path_traversal_credential_ids() -> None:
    store = SecretManagerOAuthCredentialStore(MemorySecrets())
    with pytest.raises(ValueError):
        store.get(
            "../cred",
            tenant_id="tenant",
            workspace_id="workspace",
            provider="github",
        )


def test_provider_registry_requires_unique_provider_names() -> None:
    first = build_github_oauth(
        client_id="id",
        client_secret="secret",
        redirect_uri="https://app.test/github",
    )
    second = build_github_oauth(
        client_id="id2",
        client_secret="secret2",
        redirect_uri="https://app.test/github",
    )
    registry = OAuth2ProviderRegistry()
    registry.register(first)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(second)
    assert registry.names() == ("github",)
    assert registry.get("github") is first


def test_connection_refreshes_expiring_credential_before_ingest() -> None:
    store = InMemoryOAuthCredentialStore()
    record = OAuthCredentialRecord(
        credential_id="cred",
        tenant_id="tenant",
        workspace_id="workspace",
        provider="github",
        access_token="old-access",
        refresh_token="refresh",
        token_type="Bearer",
        scopes=("read:user",),
        obtained_at=datetime.now(UTC) - timedelta(hours=1),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    store.save(record)

    oauth = build_github_oauth(
        client_id="id",
        client_secret="secret",
        redirect_uri="https://app.test/github",
    )

    class Socket:
        def ingest(self, source_id, *, tenant_id, workspace_id, credential_id):
            assert credential_id == "cred"
            assert (
                store.get(
                    "cred",
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    provider="github",
                ).access_token
                == "new-access"
            )
            return "result"

    connection = OAuth2SourceConnection(
        providers={"github": oauth},
        credentials=store,
        socket=Socket(),  # type: ignore[arg-type]
    )
    with patch.object(
        oauth,
        "refresh",
        return_value=OAuth2Token(
            access_token="new-access",
            refresh_token=None,
            scope=(),
            expires_in=3600,
        ),
    ):
        assert (
            connection.ingest(
                provider="github",
                source_id="github.rest.user",
                tenant_id="tenant",
                workspace_id="workspace",
                credential_id="cred",
            )
            == "result"
        )


def test_connection_rejects_expired_credential_without_refresh_token() -> None:
    store = InMemoryOAuthCredentialStore()
    store.save(
        OAuthCredentialRecord(
            credential_id="cred",
            tenant_id="tenant",
            workspace_id="workspace",
            provider="github",
            access_token="expired",
            refresh_token=None,
            token_type="Bearer",
            scopes=("read:user",),
            obtained_at=datetime.now(UTC) - timedelta(hours=1),
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    oauth = build_github_oauth(
        client_id="id",
        client_secret="secret",
        redirect_uri="https://app.test/github",
    )
    connection = OAuth2SourceConnection(
        providers={"github": oauth},
        credentials=store,
        socket=object(),  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="refresh token"):
        connection.ingest(
            provider="github",
            source_id="github.rest.user",
            tenant_id="tenant",
            workspace_id="workspace",
            credential_id="cred",
        )

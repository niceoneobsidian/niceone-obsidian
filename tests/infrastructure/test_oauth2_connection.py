from unittest.mock import patch

import pytest

from ois.infrastructure.oauth2 import OAuth2Token
from ois.infrastructure.oauth2_connection import (
    InMemoryOAuthCredentialStore,
    OAuth2SourceConnection,
)
from ois.infrastructure.source_gateway import SourceGateway
from ois.infrastructure.source_gateway.ledger import SQLiteSourceLedger
from ois.infrastructure.source_gateway.socket import ApiSourceSocket
from ois.integrations.github import GitHubSource, build_github_oauth


def _connection():
    store = InMemoryOAuthCredentialStore()
    ledger = SQLiteSourceLedger()
    gateway = SourceGateway(
        credentials=store,
        evidence=ledger,
        outbox=ledger,
    )
    socket = ApiSourceSocket(gateway=gateway)
    source = GitHubSource()
    socket.register(source)
    oauth = build_github_oauth(
        client_id="client",
        client_secret="secret",
        redirect_uri="https://app.test/github/callback",
    )
    service = OAuth2SourceConnection(
        providers={"github": oauth},
        credentials=store,
        socket=socket,
    )
    return service, store, ledger, source


def test_github_vertical_slice_persists_evidence_and_outbox() -> None:
    service, store, ledger, source = _connection()
    _, state = service.begin(
        provider="github",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
    )

    token = OAuth2Token(
        access_token="access-token",
        refresh_token="refresh-token",
        scope=("read:user", "user:email"),
    )
    with patch.object(service._providers["github"], "exchange_code", return_value=token):
        ref = service.complete(
            provider="github",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            state=state,
            code="temporary-code",
            credential_id="github-credential",
        )

    seen_headers: list[dict[str, str]] = []

    def fake_fetch(*, request_headers=None, **_kwargs):
        seen_headers.append(dict(request_headers or {}))
        return {"login": "niceone", "id": 123}, 200, 0.0

    source._fetch = fake_fetch  # type: ignore[method-assign]

    result = service.ingest(
        provider="github",
        source_id="github.rest.user",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        credential_id=ref.credential_id,
    )

    assert result.records == 1
    assert seen_headers == [
        {
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer access-token",
        }
    ]

    evidence = ledger.evidence(result.evidence_ids[0])
    assert evidence is not None
    assert evidence.tenant_id == "tenant-1"
    assert evidence.workspace_id == "workspace-1"
    assert evidence.payload["response"]["login"] == "niceone"
    assert "access-token" not in str(evidence.payload)

    pending = ledger.pending()
    assert len(pending) == 1
    assert pending[0].event_id == result.event_ids[0]
    assert pending[0].tenant_id == "tenant-1"
    assert pending[0].payload["evidence_id"] == evidence.evidence_id

    record = store.get(
        "github-credential",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        provider="github",
    )
    assert record.access_token == "access-token"
    assert record.refresh_token == "refresh-token"


def test_oauth_callback_state_cannot_be_replayed_or_cross_tenant() -> None:
    service, _, _, _ = _connection()
    _, state = service.begin(
        provider="github",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
    )
    token = OAuth2Token(access_token="access-token")

    with patch.object(service._providers["github"], "exchange_code", return_value=token):
        with pytest.raises(PermissionError):
            service.complete(
                provider="github",
                tenant_id="tenant-2",
                workspace_id="workspace-1",
                state=state,
                code="code",
                credential_id="github-credential",
            )

        service.complete(
            provider="github",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            state=state,
            code="code",
            credential_id="github-credential",
        )

        with pytest.raises(PermissionError):
            service.complete(
                provider="github",
                tenant_id="tenant-1",
                workspace_id="workspace-1",
                state=state,
                code="code",
                credential_id="github-credential-2",
            )


def test_ingest_cannot_use_credential_from_another_workspace() -> None:
    service, _, _, _ = _connection()
    _, state = service.begin(
        provider="github",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
    )
    token = OAuth2Token(access_token="access-token")
    with patch.object(service._providers["github"], "exchange_code", return_value=token):
        service.complete(
            provider="github",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            state=state,
            code="code",
            credential_id="github-credential",
        )

    with pytest.raises(PermissionError):
        service.ingest(
            provider="github",
            source_id="github.rest.user",
            tenant_id="tenant-1",
            workspace_id="workspace-2",
            credential_id="github-credential",
        )


def test_refresh_replaces_access_token_and_preserves_scope() -> None:
    service, store, _, _ = _connection()
    _, state = service.begin(
        provider="github",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
    )
    original = OAuth2Token(
        access_token="old-access",
        refresh_token="old-refresh",
        scope=("read:user",),
    )
    with patch.object(service._providers["github"], "exchange_code", return_value=original):
        service.complete(
            provider="github",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            state=state,
            code="code",
            credential_id="github-credential",
        )

    refreshed = OAuth2Token(
        access_token="new-access",
        refresh_token="new-refresh",
        scope=("read:user",),
    )
    with patch.object(service._providers["github"], "refresh", return_value=refreshed):
        service.refresh(
            provider="github",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            credential_id="github-credential",
        )

    record = store.get(
        "github-credential",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        provider="github",
    )
    assert record.access_token == "new-access"
    assert record.refresh_token == "new-refresh"
    assert record.scopes == ("read:user",)

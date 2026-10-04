from urllib.parse import parse_qs, urlparse

from ois.infrastructure.source_adapters.http import HttpSourceAdapter
from ois.infrastructure.source_gateway import (
    ApiSourceSocket,
    InMemoryCredentialResolver,
    SourceGateway,
)
from ois.integrations.github import GitHubSource, build_github_oauth
from ois.integrations.google import GoogleDriveSource, build_google_oauth
from ois.integrations.meta import MetaFacebookSource, build_meta_oauth
from ois.integrations.tiktok import build_tiktok_oauth


def test_phase_a_provider_sources_use_governed_auth() -> None:
    assert GitHubSource().source_id == "github.rest.user"
    assert MetaFacebookSource().source_id == "meta.graph.me"
    assert GoogleDriveSource().source_id == "google.drive.files"
    assert build_tiktok_oauth(
        client_key="key", client_secret="secret", redirect_uri="https://app.test/callback"
    ).config.provider == "tiktok"
    assert build_github_oauth(
        client_id="id", client_secret="secret", redirect_uri="https://app.test/callback"
    ).config.provider == "github"
    assert build_meta_oauth(
        app_id="id", app_secret="secret", redirect_uri="https://app.test/callback"
    ).config.provider == "meta"
    assert build_google_oauth(
        client_id="id", client_secret="secret", redirect_uri="https://app.test/callback"
    ).config.provider == "google"


def test_tiktok_authorization_uses_comma_separated_scopes() -> None:
    provider = build_tiktok_oauth(
        client_key="key",
        client_secret="secret",
        redirect_uri="https://app.test/callback",
    )
    url, _ = provider.authorization_url(tenant_id="tenant", workspace_id="workspace")
    query = parse_qs(urlparse(url).query)
    assert query["scope"] == ["user.info.basic,video.list"]


def test_google_drive_ingest_follows_next_page_token(monkeypatch) -> None:
    source = GoogleDriveSource(page_size=2)
    pages = iter(
        (
            {"files": [{"id": "one"}], "nextPageToken": "next-page"},
            {"files": [{"id": "two"}]},
        )
    )
    requested_urls: list[str] = []

    def fake_fetch(credential=None, *, url=None):
        requested_urls.append(url or "")
        return next(pages)

    monkeypatch.setattr(source, "_fetch", fake_fetch)
    result = source.ingest(
        tenant_id="tenant",
        workspace_id="workspace",
        gateway=SourceGateway(),
    )
    assert result.records == 2
    assert requested_urls[0].endswith("fields=nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink)")
    assert "pageToken=next-page" in requested_urls[1]


def test_authenticated_http_health_uses_credential(monkeypatch) -> None:
    adapter = GitHubSource()
    seen: list[str] = []

    def fake_fetch(credential=None, *, url=None):
        assert credential is not None
        seen.append(credential.secret)
        return {"login": "niceone"}

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    socket = ApiSourceSocket(
        gateway=SourceGateway(
            credentials=InMemoryCredentialResolver({"github-token": "token-value"})
        )
    )
    socket.register(adapter)

    unauthenticated = socket.health("github.rest.user")
    authenticated = socket.health(
        "github.rest.user",
        tenant_id="tenant",
        workspace_id="workspace",
        credential_id="github-token",
    )
    status = socket.status(
        "github.rest.user",
        tenant_id="tenant",
        workspace_id="workspace",
        credential_id="github-token",
    )

    assert unauthenticated[0].healthy is False
    assert authenticated[0].healthy is True
    assert status.healthy is True
    assert seen == ["token-value", "token-value"]


def test_http_source_adapter_health_accepts_bearer_credential(monkeypatch) -> None:
    adapter = HttpSourceAdapter(
        source_id="test.api",
        url="https://example.test",
        auth_scheme=AuthScheme.BEARER,
    )

    def fake_fetch(credential=None, *, url=None):
        assert credential is not None
        assert credential.secret == "access-token"
        return {}

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    assert adapter.health().healthy is False

    from ois.infrastructure.source_gateway.auth import CredentialMaterial

    assert adapter.health(CredentialMaterial("access-token")).healthy is True

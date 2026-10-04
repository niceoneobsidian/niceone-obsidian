"""Opt-in real-provider smoke tests for Phase A.

These tests never run in normal CI. Set OIS_LIVE_PHASE_A=1 plus the provider
access-token variables in a protected local/CI environment to validate the
real external APIs through the governed source boundary.
"""

from __future__ import annotations

import os

import pytest

from ois.infrastructure.source_gateway import InMemoryCredentialResolver, SourceGateway
from ois.infrastructure.source_gateway.socket import ApiSourceSocket
from ois.integrations.github import GitHubSource
from ois.integrations.google import GoogleDriveSource
from ois.integrations.meta import MetaFacebookSource
from ois.integrations.tiktok import TikTokDisplayClient, TikTokSource


pytestmark = pytest.mark.skipif(
    os.getenv("OIS_LIVE_PHASE_A") != "1",
    reason="set OIS_LIVE_PHASE_A=1 to run external Phase A smoke tests",
)


def _token(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


def _socket(provider: str, token: str, source) -> ApiSourceSocket:
    socket = ApiSourceSocket(
        gateway=SourceGateway(
            credentials=InMemoryCredentialResolver({f"{provider}-live": token})
        )
    )
    socket.register(source)
    return socket


def test_live_github_authenticated_source() -> None:
    socket = _socket("github", _token("OIS_LIVE_GITHUB_ACCESS_TOKEN"), GitHubSource())
    result = socket.ingest(
        "github.rest.user",
        tenant_id="live-test",
        workspace_id="phase-a",
        credential_id="github-live",
    )
    assert result.records >= 1


def test_live_meta_authenticated_source() -> None:
    socket = _socket("meta", _token("OIS_LIVE_META_ACCESS_TOKEN"), MetaFacebookSource())
    result = socket.ingest(
        "meta.graph.me",
        tenant_id="live-test",
        workspace_id="phase-a",
        credential_id="meta-live",
    )
    assert result.records >= 1


def test_live_google_authenticated_source() -> None:
    socket = _socket("google", _token("OIS_LIVE_GOOGLE_ACCESS_TOKEN"), GoogleDriveSource())
    result = socket.ingest(
        "google.drive.files",
        tenant_id="live-test",
        workspace_id="phase-a",
        credential_id="google-live",
    )
    assert result.records >= 1


def test_live_tiktok_authenticated_source() -> None:
    token = _token("OIS_LIVE_TIKTOK_ACCESS_TOKEN")
    gateway = SourceGateway()
    client = TikTokDisplayClient(token)
    source = TikTokSource(
        client=client,
        gateway=gateway,
        get_cursor=lambda: None,
        advance_cursor=lambda _cursor: None,
    )
    result = source.ingest_pages(
        tenant_id="live-test",
        workspace_id="phase-a",
        credential_id="tiktok-live",
        max_pages=1,
        max_count=1,
    )
    assert result.pages == 1

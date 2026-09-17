from __future__ import annotations

import os
from unittest.mock import patch

from ois.domains.social_intelligence.registry import build_social_tool_registry
from ois.domains.social_intelligence.schemas import SocialProfile, SocialPublishRequest
from ois.domains.social_intelligence.providers import BundleSocialAdapter, SociaVaultAdapter


def test_provider_registry_is_versioned_and_secret_free() -> None:
    registry = build_social_tool_registry()
    entries = registry.snapshot()
    assert [entry.id for entry in entries] == ["tool.social.bundle_social", "tool.social.sociavault"]
    assert all(entry.version == "1.0.0" for entry in entries)
    assert all("API_KEY" not in repr(entry.metadata) for entry in entries)


def test_sociavault_normalization() -> None:
    adapter = SociaVaultAdapter()
    payload = {"data": {"id": "42", "username": "creator", "nickname": "Creator", "follower_count": 1234}}
    with patch.object(adapter._client, "_request", return_value=payload):
        profile = adapter.tiktok_profile("creator")
    assert isinstance(profile, SocialProfile)
    assert profile.provider == "sociavault"
    assert profile.platform == "tiktok"
    assert profile.handle == "creator"
    assert profile.followers == 1234


def test_bundle_social_publish_request_contract() -> None:
    request = SocialPublishRequest(
        team_id="team_test",
        status="DRAFT",
        platforms=["INSTAGRAM"],
        data={"INSTAGRAM": {"type": "POST", "text": "test"}},
    )
    assert request.team_id == "team_test"
    assert request.platforms == ["INSTAGRAM"]


def test_bundle_social_normalization() -> None:
    adapter = BundleSocialAdapter()
    payload = {"data": {"id": "post_123", "status": "DRAFT", "results": {"INSTAGRAM": {"status": "DRAFT"}}}}
    with patch.object(adapter._client, "_request", return_value=payload):
        result = adapter.create_post(SocialPublishRequest(team_id="team_test", platforms=["INSTAGRAM"], data={"INSTAGRAM": {"type": "POST", "text": "test"}}))
    assert result.provider == "bundle_social"
    assert result.external_post_id == "post_123"
    assert result.status == "DRAFT"


def test_credentials_are_not_read_at_import_time() -> None:
    with patch.dict(os.environ, {}, clear=True):
        adapter = SociaVaultAdapter()
        try:
            adapter.tiktok_profile("creator")
        except Exception as exc:
            assert "SOCIAVAULT_API_KEY" in str(exc)

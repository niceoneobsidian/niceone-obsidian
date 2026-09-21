from __future__ import annotations

import os
from unittest.mock import patch

from ois.domains.social_intelligence.providers import (
    BundleSocialAdapter,
    SociaVaultAdapter,
)
from ois.domains.social_intelligence.registry import build_social_tool_registry
from ois.domains.social_intelligence.schemas import (
    SocialMetric,
    SocialProfile,
    SocialPublishRequest,
)


def test_provider_registry_is_versioned_and_secret_free() -> None:
    registry = build_social_tool_registry()
    entries = registry.snapshot()

    assert {entry.id for entry in entries} == {
        "tool.social.bundle_social",
        "tool.social.sociavault",
    }
    assert all(entry.version == "1.0.0" for entry in entries)

    contracts = {entry.id: entry.contract for entry in entries}
    assert contracts["tool.social.sociavault"].secrets_required == (
        "SOCIAVAULT_API_KEY",
    )
    assert contracts["tool.social.bundle_social"].secrets_required == (
        "BUNDLE_SOCIAL_API_KEY",
    )
    assert all("API_KEY" not in repr(entry.contract) for entry in entries)


def test_sociavault_normalization() -> None:
    adapter = SociaVaultAdapter()
    payload = {
        "data": {
            "id": "42",
            "username": "creator",
            "nickname": "Creator",
            "follower_count": 1234,
        }
    }
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
    payload = {
        "data": {
            "id": "post_123",
            "status": "DRAFT",
            "results": {"INSTAGRAM": {"status": "DRAFT"}},
        }
    }
    request = SocialPublishRequest(
        team_id="team_test",
        platforms=["INSTAGRAM"],
        data={"INSTAGRAM": {"type": "POST", "text": "test"}},
    )
    with patch.object(adapter._client, "_request", return_value=payload):
        result = adapter.create_post(request)

    assert result.provider == "bundle_social"
    assert result.external_post_id == "post_123"
    assert result.status == "DRAFT"


def test_bundle_social_analytics_normalization() -> None:
    adapter = BundleSocialAdapter()
    payload = {
        "data": {
            "metrics": {
                "likes": 10,
                "comments": 2,
                "views": 500,
                "watch_time_seconds": 42.5,
            }
        }
    }
    with patch.object(adapter._client, "_request", return_value=payload):
        result = adapter.post_analytics("post_123", "TIKTOK")

    assert isinstance(result.metrics, SocialMetric)
    assert result.metrics.likes == 10
    assert result.metrics.comments == 2
    assert result.metrics.views == 500
    assert result.metrics.watch_time_seconds == 42.5


def test_credentials_are_not_read_at_import_time() -> None:
    with patch.dict(os.environ, {}, clear=True):
        adapter = SociaVaultAdapter()
        try:
            adapter.tiktok_profile("creator")
        except Exception as exc:
            assert "SOCIAVAULT_API_KEY" in str(exc)

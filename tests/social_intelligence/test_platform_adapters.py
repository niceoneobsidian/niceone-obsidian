from datetime import UTC, datetime

from ois.domains.social_intelligence.platform_adapters import (
    LinkedInPostsAdapter,
    OAuthTokenProvider,
    TikTokContentPostingAdapter,
)
from ois.domains.social_intelligence.schemas import PublishIntent


def test_tiktok_adapter_targets_current_content_posting_endpoint(monkeypatch) -> None:
    calls = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"data":{"publish_id":"test"},"error":{"code":"ok"}}'

    def fake_urlopen(request, timeout):
        calls["url"] = request.full_url
        calls["method"] = request.method
        calls["authorization"] = request.headers.get("Authorization")
        calls["body"] = request.data
        calls["timeout"] = timeout
        return Response()

    monkeypatch.setattr(
        "ois.domains.social_intelligence.platform_adapters.urlopen", fake_urlopen
    )
    adapter = TikTokContentPostingAdapter(
        OAuthTokenProvider(lambda account: "token-1")
    )
    result = adapter.publish(
        PublishIntent(
            platform="tiktok",
            account_ref="account-1",
            content={
                "video_url": "https://media.example/video.mp4",
                "caption": "test",
            },
            scheduled_for=datetime.now(UTC),
            requires_approval=False,
        )
    )

    assert result["data"]["publish_id"] == "test"
    assert calls["url"] == "https://open.tiktokapis.com/v2/post/publish/video/init/"
    assert calls["method"] == "POST"
    assert calls["authorization"] == "Bearer token-1"
    assert calls["timeout"] == 30


def test_linkedin_posts_adapter_uses_current_posts_api(monkeypatch) -> None:
    calls = {}

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b""

    def fake_urlopen(request, timeout):
        calls["url"] = request.full_url
        calls["authorization"] = request.headers.get("Authorization")
        calls["version"] = request.headers.get("Linkedin-Version")
        calls["protocol"] = request.headers.get("X-Restli-Protocol-Version")
        calls["body"] = request.data
        return Response()

    monkeypatch.setattr(
        "ois.domains.social_intelligence.platform_adapters.urlopen", fake_urlopen
    )
    adapter = LinkedInPostsAdapter(
        OAuthTokenProvider(lambda account: "token-2"),
        api_version="202604",
    )
    result = adapter.publish(
        PublishIntent(
            platform="linkedin",
            account_ref="account-2",
            content={"author": "urn:li:organization:1", "commentary": "hello"},
        )
    )

    assert result["status"] == 201
    assert calls["url"] == "https://api.linkedin.com/rest/posts"
    assert calls["authorization"] == "Bearer token-2"
    assert calls["version"] == "202604"
    assert calls["protocol"] == "2.0.0"

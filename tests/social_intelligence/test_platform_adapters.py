from datetime import UTC, datetime

from ois.domains.social_intelligence.platform_adapters import OAuthTokenProvider, TikTokContentPostingAdapter
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

    monkeypatch.setattr("ois.domains.social_intelligence.platform_adapters.urlopen", fake_urlopen)
    adapter = TikTokContentPostingAdapter(OAuthTokenProvider(lambda account: "token-1"))
    result = adapter.publish(PublishIntent(
        platform="tiktok",
        account_ref="account-1",
        content={"video_url": "https://media.example/video.mp4", "caption": "test"},
        scheduled_for=datetime.now(UTC),
        requires_approval=False,
    ))

    assert result["data"]["publish_id"] == "test"
    assert calls["url"] == "https://open.tiktokapis.com/v2/post/publish/video/init/"
    assert calls["method"] == "POST"
    assert calls["authorization"] == "Bearer token-1"
    assert calls["timeout"] == 30

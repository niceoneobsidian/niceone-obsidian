"""Real social platform HTTP adapters.

Credentials are injected by OIS; they are never accepted as capability payloads.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .connectors import SocialConnector
from .schemas import PublishIntent, SocialEvent


class PlatformAPIError(RuntimeError):
    """Raised when a platform API request fails."""


@dataclass(frozen=True)
class OAuthTokenProvider:
    get_token: Callable[[str], str]


class TikTokContentPostingAdapter(SocialConnector):
    """TikTok Content Posting API adapter for URL-based video direct posting."""

    platform = "tiktok"
    base_url = "https://open.tiktokapis.com"

    def __init__(self, token_provider: OAuthTokenProvider) -> None:
        self._tokens = token_provider

    def capabilities(self) -> set[str]:
        return {"read_events", "publish_video"}

    def normalize_event(self, payload: Mapping[str, object]) -> SocialEvent:
        from .connectors import GenericSocialConnector

        return GenericSocialConnector("tiktok").normalize_event(payload)

    def publish(self, intent: PublishIntent) -> dict[str, object]:
        errors = self.validate_publish(intent)
        if errors:
            raise ValueError("invalid publish intent: " + "; ".join(errors))
        video_url = intent.content.get("video_url")
        if not isinstance(video_url, str) or not video_url.startswith("https://"):
            raise ValueError("TikTok direct post requires an HTTPS video_url")
        token = self._tokens.get_token(intent.account_ref)
        post_info = dict(intent.content.get("post_info", {}))
        post_info.setdefault("title", intent.content.get("caption", ""))
        post_info.setdefault("privacy_level", "SELF_ONLY")
        payload = {
            "post_info": post_info,
            "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
        }
        return self._request("/v2/post/publish/video/init/", token, payload)

    @staticmethod
    def _request(
        path: str,
        token: str,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        request = Request(
            f"{TikTokContentPostingAdapter.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise PlatformAPIError(f"TikTok API request failed: {exc}") from exc
        if not isinstance(body, dict):
            raise PlatformAPIError("TikTok API returned a non-object response")
        error = body.get("error")
        if isinstance(error, Mapping) and error.get("code") not in (None, "ok"):
            raise PlatformAPIError(f"TikTok API error: {error}")
        return body


class LinkedInPostsAdapter(SocialConnector):
    """LinkedIn Posts API adapter for organic text/video/image post metadata."""

    platform = "linkedin"
    base_url = "https://api.linkedin.com/rest/posts"

    def __init__(self, token_provider: OAuthTokenProvider, *, api_version: str) -> None:
        if not api_version:
            raise ValueError("LinkedIn API version is required")
        self._tokens = token_provider
        self._api_version = api_version

    def capabilities(self) -> set[str]:
        return {"read_events", "publish"}

    def normalize_event(self, payload: Mapping[str, object]) -> SocialEvent:
        from .connectors import GenericSocialConnector

        return GenericSocialConnector("linkedin").normalize_event(payload)

    def publish(self, intent: PublishIntent) -> dict[str, object]:
        errors = self.validate_publish(intent)
        if errors:
            raise ValueError("invalid publish intent: " + "; ".join(errors))
        token = self._tokens.get_token(intent.account_ref)
        content = intent.content
        payload = {
            "author": str(content["author"]),
            "commentary": str(content.get("commentary", content.get("caption", ""))),
            "visibility": str(content.get("visibility", "PUBLIC")),
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        return self._request(token, payload)

    def _request(self, token: str, payload: Mapping[str, object]) -> dict[str, object]:
        request = Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
                "Linkedin-Version": self._api_version,
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {"status": response.status}
        except Exception as exc:
            raise PlatformAPIError(f"LinkedIn API request failed: {exc}") from exc


class OAuthJSONPlatformAdapter(SocialConnector):
    """Configurable JSON REST adapter for approved platform APIs."""

    def __init__(
        self,
        platform: str,
        publish_url: str,
        token_provider: OAuthTokenProvider,
        payload_builder: Callable[[PublishIntent], Mapping[str, object]],
    ) -> None:
        self.platform = platform
        self._publish_url = publish_url
        self._tokens = token_provider
        self._payload_builder = payload_builder

    def capabilities(self) -> set[str]:
        return {"read_events", "publish"}

    def normalize_event(self, payload: Mapping[str, object]) -> SocialEvent:
        from .connectors import GenericSocialConnector

        return GenericSocialConnector(self.platform).normalize_event(payload)

    def publish(self, intent: PublishIntent) -> dict[str, object]:
        errors = self.validate_publish(intent)
        if errors:
            raise ValueError("invalid publish intent: " + "; ".join(errors))
        token = self._tokens.get_token(intent.account_ref)
        request = Request(
            self._publish_url,
            data=json.dumps(self._payload_builder(intent)).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise PlatformAPIError(f"{self.platform} API request failed: {exc}") from exc
        if not isinstance(body, dict):
            raise PlatformAPIError(f"{self.platform} API returned a non-object response")
        return body

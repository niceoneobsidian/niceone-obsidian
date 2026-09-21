"""Provider adapters for the first Social Intelligence integrations.

Credentials are resolved from environment variables at invocation time. No secret is
stored in the registry, manifest, prompts, or source tree.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from .schemas import (
    SocialAnalytics,
    SocialMetric,
    SocialPost,
    SocialProfile,
    SocialPublishRequest,
    SocialPublishResult,
    SocialSearchResult,
)


class ProviderError(RuntimeError):
    """A provider request failed or returned an invalid response."""


class _HttpClient:
    def __init__(
        self,
        base_url: str,
        api_key_env: str,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = os.getenv(self.api_key_env)
        if not key:
            raise ProviderError(f"missing required credential: {self.api_key_env}")

        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            query = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}
            )
            url += f"?{query}"

        data = json.dumps(body).encode() if body is not None else None
        headers = {"Accept": "application/json", "x-api-key": key}
        if body is not None:
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode())
        except Exception as exc:  # pragma: no cover
            raise ProviderError(
                f"provider request failed: {type(exc).__name__}: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise ProviderError("provider returned a non-object JSON response")
        return payload


class SociaVaultAdapter:
    """Read-only Social Intelligence adapter backed by SociaVault."""

    provider_id = "sociavault"
    base_url = "https://api.sociavault.com/v1"

    def __init__(self, timeout: float = 30.0) -> None:
        self._client = _HttpClient(
            self.base_url,
            "SOCIAVAULT_API_KEY",
            timeout,
        )

    def tiktok_profile(self, handle: str) -> SocialProfile:
        payload = self._client._request(
            "GET",
            "/scrape/tiktok/profile",
            params={"handle": handle},
        )
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise ProviderError("invalid SociaVault profile payload")

        return SocialProfile(
            provider=self.provider_id,
            platform="tiktok",
            external_id=str(data["id"]) if data.get("id") is not None else None,
            handle=data.get("username") or data.get("handle") or handle,
            display_name=data.get("nickname") or data.get("display_name"),
            bio=data.get("bio"),
            profile_url=data.get("profile_url"),
            followers=data.get("followers") or data.get("follower_count"),
            following=data.get("following") or data.get("following_count"),
            posts_count=data.get("video_count") or data.get("posts_count"),
            verified=data.get("verified"),
            raw=data,
            observed_at=datetime.now(UTC),
        )

    def tiktok_search(
        self,
        query: str,
        kind: str = "keyword",
    ) -> SocialSearchResult:
        allowed = {
            "users": "/scrape/tiktok/search/users",
            "hashtag": "/scrape/tiktok/search/hashtag",
            "keyword": "/scrape/tiktok/search/keyword",
            "top": "/scrape/tiktok/search/top",
        }
        path = allowed.get(kind)
        if path is None:
            raise ValueError(f"unsupported TikTok search kind: {kind}")

        payload = self._client._request(
            "GET",
            path,
            params={"query": query},
        )
        data = payload.get("data", payload)
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("results", [])
        else:
            items = []

        profiles: list[SocialProfile] = []
        posts: list[SocialPost] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            if kind == "users":
                profiles.append(
                    SocialProfile(
                        provider=self.provider_id,
                        platform="tiktok",
                        external_id=(
                            str(item["id"]) if item.get("id") is not None else None
                        ),
                        handle=item.get("username") or item.get("unique_id"),
                        display_name=item.get("nickname") or item.get("display_name"),
                        followers=item.get("followers") or item.get("follower_count"),
                        raw=item,
                    )
                )
            else:
                posts.append(
                    SocialPost(
                        provider=self.provider_id,
                        platform="tiktok",
                        external_id=str(
                            item.get("id")
                            or item.get("video_id")
                            or item.get("aweme_id")
                        ),
                        author_handle=(
                            item.get("username")
                            or item.get("author_username")
                        ),
                        text=(
                            item.get("description")
                            or item.get("desc")
                            or item.get("text")
                        ),
                        url=item.get("url") or item.get("video_url"),
                        media_type="video",
                        raw=item,
                        observed_at=datetime.now(UTC),
                    )
                )

        return SocialSearchResult(
            provider=self.provider_id,
            platform="tiktok",
            query=query,
            profiles=profiles,
            posts=posts,
            raw=payload,
            observed_at=datetime.now(UTC),
        )


class BundleSocialAdapter:
    """Controlled publishing and analytics adapter backed by bundle.social."""

    provider_id = "bundle_social"
    base_url = "https://api.bundle.social/api/v1"

    def __init__(self, timeout: float = 30.0) -> None:
        self._client = _HttpClient(
            self.base_url,
            "BUNDLE_SOCIAL_API_KEY",
            timeout,
        )

    def create_post(self, request: SocialPublishRequest) -> SocialPublishResult:
        payload = self._client._request(
            "POST",
            "/post",
            body={
                "teamId": request.team_id,
                "title": request.title,
                "postDate": request.post_date.isoformat() if request.post_date else None,
                "status": request.status,
                "socialAccountTypes": request.platforms,
                "data": request.data,
            },
        )
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise ProviderError("invalid bundle.social post response")

        return SocialPublishResult(
            provider=self.provider_id,
            external_post_id=str(data["id"]) if data.get("id") is not None else None,
            status=str(data.get("status", "UNKNOWN")),
            platform_results=data.get("platforms", data.get("results", {})) or {},
            raw=payload,
            observed_at=datetime.now(UTC),
        )

    def post_analytics(
        self,
        post_id: str,
        platform: str,
    ) -> SocialAnalytics:
        payload = self._client._request(
            "GET",
            "/analytics/post",
            params={
                "postId": post_id,
                "platformType": platform,
            },
        )
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise ProviderError("invalid bundle.social analytics response")

        metrics_payload = data.get("metrics", data)
        if not isinstance(metrics_payload, dict):
            raise ProviderError("invalid bundle.social analytics metrics")

        metrics = SocialMetric.model_validate(metrics_payload)

        return SocialAnalytics(
            provider=self.provider_id,
            platform=platform,
            external_post_id=post_id,
            metrics=metrics,
            raw=payload,
            observed_at=datetime.now(UTC),
        )

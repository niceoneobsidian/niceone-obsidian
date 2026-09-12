from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .models import (
    YouTubeAnalyticsRow,
    YouTubeCaptionTrack,
    YouTubeChannel,
    YouTubePage,
    YouTubeSearchResult,
    YouTubeVideo,
)

YOUTUBE_DATA_SCOPE = "https://www.googleapis.com/auth/youtube"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
YOUTUBE_ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_ANALYTICS_BASE = "https://youtubeanalytics.googleapis.com/v2"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


@dataclass(frozen=True)
class YouTubeOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...] = (YOUTUBE_READONLY_SCOPE,)

    def authorization_url(self, state: str) -> str:
        query = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.scopes),
                "access_type": "offline",
                "state": state,
                "prompt": "consent",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        payload = urllib.parse.urlencode(
            {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }
        ).encode()
        request = urllib.request.Request(
            GOOGLE_TOKEN_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())


class YouTubeClient:
    """Provider adapter for governed YouTube API access.

    Credentials/tokens are passed at runtime and must come from OIS secret
    management. No credential persistence is performed here.
    """

    def __init__(self, *, api_key: str | None = None, access_token: str | None = None) -> None:
        if not api_key and not access_token:
            raise ValueError("YouTubeClient requires api_key or access_token")
        self.api_key = api_key
        self.access_token = access_token

    def _request(
        self,
        base: str,
        resource: str,
        *,
        params: dict[str, Any] | None = None,
        method: str = "GET",
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query = dict(params or {})
        if self.api_key:
            query["key"] = self.api_key
        url = f"{base}/{resource}?{urllib.parse.urlencode(query, doseq=True)}"
        headers = {"Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        data = json.dumps(body).encode() if body is not None else None
        if data:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode())
        except Exception as exc:
            raise RuntimeError(f"YouTube API request failed: {resource}: {exc}") from exc

    @staticmethod
    def _page_token(params: dict[str, Any], page_token: str | None) -> dict[str, Any]:
        result = dict(params)
        if page_token:
            result["pageToken"] = page_token
        return result

    def search_videos(self, query: str, *, max_results: int = 25, page_token: str | None = None) -> YouTubePage[YouTubeSearchResult]:
        payload = self._request(
            YOUTUBE_API_BASE,
            "search",
            params=self._page_token(
                {"part": "snippet", "q": query, "type": "video", "maxResults": max_results},
                page_token,
            ),
        )
        items = [
            YouTubeSearchResult(
                kind=item.get("id", {}).get("kind"),
                video_id=item.get("id", {}).get("videoId"),
                channel_id=item.get("id", {}).get("channelId"),
                playlist_id=item.get("id", {}).get("playlistId"),
                title=item.get("snippet", {}).get("title"),
                description=item.get("snippet", {}).get("description"),
                published_at=item.get("snippet", {}).get("publishedAt"),
            )
            for item in payload.get("items", [])
        ]
        page = payload.get("pageInfo", {})
        return YouTubePage(
            items=items,
            next_page_token=payload.get("nextPageToken"),
            prev_page_token=payload.get("prevPageToken"),
            total_results=page.get("totalResults"),
            results_per_page=page.get("resultsPerPage"),
        )

    def get_channels(self, channel_ids: list[str]) -> YouTubePage[YouTubeChannel]:
        payload = self._request(YOUTUBE_API_BASE, "channels", params={"part": "snippet,statistics", "id": ",".join(channel_ids)})
        items = []
        for item in payload.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            items.append(
                YouTubeChannel(
                    id=item.get("id"),
                    title=snippet.get("title"),
                    description=snippet.get("description"),
                    custom_url=snippet.get("customUrl"),
                    published_at=snippet.get("publishedAt"),
                    subscriber_count=int(stats["subscriberCount"]) if "subscriberCount" in stats else None,
                    video_count=int(stats["videoCount"]) if "videoCount" in stats else None,
                    view_count=int(stats["viewCount"]) if "viewCount" in stats else None,
                )
            )
        return YouTubePage(items=items)

    def get_videos(self, video_ids: list[str]) -> YouTubePage[YouTubeVideo]:
        payload = self._request(YOUTUBE_API_BASE, "videos", params={"part": "snippet,contentDetails,statistics", "id": ",".join(video_ids)})
        items = []
        for item in payload.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            content = item.get("contentDetails", {})
            items.append(
                YouTubeVideo(
                    id=item.get("id"),
                    channel_id=snippet.get("channelId"),
                    channel_title=snippet.get("channelTitle"),
                    title=snippet.get("title"),
                    description=snippet.get("description"),
                    published_at=snippet.get("publishedAt"),
                    duration=content.get("duration"),
                    category_id=snippet.get("categoryId"),
                    tags=snippet.get("tags", []),
                    view_count=int(stats["viewCount"]) if "viewCount" in stats else None,
                    like_count=int(stats["likeCount"]) if "likeCount" in stats else None,
                    comment_count=int(stats["commentCount"]) if "commentCount" in stats else None,
                )
            )
        return YouTubePage(items=items)

    def list_captions(self, video_id: str) -> YouTubePage[YouTubeCaptionTrack]:
        payload = self._request(YOUTUBE_API_BASE, "captions", params={"part": "snippet", "videoId": video_id})
        items = [
            YouTubeCaptionTrack(
                id=item["id"],
                video_id=video_id,
                language=item.get("snippet", {}).get("language"),
                name=item.get("snippet", {}).get("name"),
                is_draft=item.get("snippet", {}).get("isDraft", False),
            )
            for item in payload.get("items", [])
        ]
        return YouTubePage(items=items)

    def download_caption(self, caption_id: str, *, tfmt: str = "vtt") -> str:
        return str(self._request(YOUTUBE_API_BASE, f"captions/{caption_id}", params={"tfmt": tfmt}))

    def update_caption(self, caption_id: str, caption: dict[str, Any]) -> dict[str, Any]:
        return self._request(YOUTUBE_API_BASE, "captions", params={"part": "snippet"}, method="PUT", body={"id": caption_id, "snippet": caption})

    def delete_caption(self, caption_id: str) -> dict[str, Any]:
        return self._request(YOUTUBE_API_BASE, f"captions/{caption_id}", method="DELETE")

    def analytics_report(
        self,
        *,
        ids: str,
        start_date: str,
        end_date: str,
        metrics: str,
        dimensions: str | None = None,
        filters: str | None = None,
    ) -> list[YouTubeAnalyticsRow]:
        params: dict[str, Any] = {"ids": ids, "startDate": start_date, "endDate": end_date, "metrics": metrics}
        if dimensions:
            params["dimensions"] = dimensions
        if filters:
            params["filters"] = filters
        payload = self._request(YOUTUBE_ANALYTICS_BASE, "reports", params=params)
        headers = [column["name"] for column in payload.get("columnHeaders", [])]
        return [YouTubeAnalyticsRow(values=dict(zip(headers, row, strict=False))) for row in payload.get("rows", [])]

    def list_live_broadcasts(self, *, page_token: str | None = None, max_results: int = 25) -> dict[str, Any]:
        return self._request(
            YOUTUBE_API_BASE,
            "liveBroadcasts",
            params=self._page_token({"part": "snippet,contentDetails,status", "mine": "true", "maxResults": max_results}, page_token),
        )

    def transition_live_broadcast(self, broadcast_id: str, status: str) -> dict[str, Any]:
        return self._request(
            YOUTUBE_API_BASE,
            "liveBroadcasts/transition",
            params={"broadcastStatus": status, "id": broadcast_id, "part": "snippet,contentDetails,status"},
        )

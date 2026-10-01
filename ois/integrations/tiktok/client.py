"""Small, dependency-free TikTok Display API v2 client."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "https://open.tiktokapis.com"
VIDEO_FIELDS = (
    "id,create_time,cover_image_url,share_url,video_description,duration,"
    "height,width,title,embed_link,like_count,comment_count,share_count,view_count,is_aigc"
)


class TikTokAPIError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable


@dataclass(frozen=True)
class TikTokPage:
    videos: tuple[dict[str, Any], ...]
    cursor: str | None
    has_more: bool
    raw: dict[str, Any]


class TikTokDisplayClient:
    def __init__(
        self,
        access_token: str,
        *,
        timeout: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        opener: Any = urlopen,
    ) -> None:
        self._token = access_token
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._opener = opener

    def _request(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{API_BASE}{path}?{urlencode({'fields': VIDEO_FIELDS})}"
        request = Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        for attempt in range(self._max_retries + 1):
            try:
                with self._opener(request, timeout=self._timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                error = payload.get("error", {})
                if error and error.get("code") not in (None, "ok"):
                    raise TikTokAPIError(str(error.get("message", error)), retryable=False)
                return cast(dict[str, Any], payload)
            except HTTPError as exc:
                retryable = exc.code == 429 or exc.code >= 500
                if not retryable or attempt == self._max_retries:
                    raise TikTokAPIError(
                        f"TikTok HTTP {exc.code}", status=exc.code, retryable=retryable
                    ) from exc
            except (URLError, TimeoutError) as exc:
                if attempt == self._max_retries:
                    raise TikTokAPIError("TikTok transport failure", retryable=True) from exc
            time.sleep(self._backoff * (2**attempt))
        raise AssertionError("unreachable")

    def list_videos(self, *, cursor: str | None = None, max_count: int = 20) -> TikTokPage:
        if not 1 <= max_count <= 20:
            raise ValueError("Display API video/list max_count must be between 1 and 20")
        body: dict[str, Any] = {"max_count": max_count}
        if cursor is not None:
            body["cursor"] = int(cursor)
        raw = self._request("/v2/video/list/", body)
        data = raw.get("data", {})
        return TikTokPage(
            videos=tuple(data.get("videos", ())),
            cursor=str(data["cursor"]) if data.get("cursor") is not None else None,
            has_more=bool(data.get("has_more", False)),
            raw=raw,
        )

    def query_videos(self, video_ids: list[str]) -> TikTokPage:
        if not video_ids or len(video_ids) > 20:
            raise ValueError("video/query accepts 1-20 video IDs")
        raw = self._request("/v2/video/query/", {"filters": {"video_ids": video_ids}})
        data = raw.get("data", {})
        return TikTokPage(
            videos=tuple(data.get("videos", ())),
            cursor=None,
            has_more=False,
            raw=raw,
        )

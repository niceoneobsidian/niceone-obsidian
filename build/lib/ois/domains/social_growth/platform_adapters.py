"""Concrete HTTP adapters for supported social APIs.

Credentials are injected by deployment configuration; no secrets are stored in
OIS. Calls are made only when an authorized OIS capability invokes the adapter.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .connectors import SocialConnector
from .schemas import PublishIntent, SocialEvent


class SocialAPIError(RuntimeError):
    """External social API request failed."""


class BearerHTTPClient:
    def __init__(self, token: str, *, timeout: float = 30.0) -> None:
        if not token:
            raise ValueError("API token is required")
        self._token = token
        self._timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request_headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
        if headers:
            request_headers.update(headers)
        request = Request(url, data=body, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=self._timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except (HTTPError, URLError) as exc:
            raise SocialAPIError(f"social API request failed: {exc}") from exc


class XConnector(SocialConnector):
    platform = "x"

    def __init__(self, token: str | None = None) -> None:
        self._http = BearerHTTPClient(token or os.environ.get("OIS_X_BEARER_TOKEN", ""))

    def capabilities(self) -> set[str]:
        return {"publish", "read_events"}

    def normalize_event(self, payload: Mapping[str, Any]) -> SocialEvent:
        return SocialEvent(
            platform="x",
            event_type="post",
            occurred_at=datetime.now(UTC),
            external_id=str(payload.get("id")) if payload.get("id") else None,
            text=payload.get("text"),
            raw=dict(payload),
        )

    def publish(self, intent: PublishIntent) -> dict[str, Any]:
        errors = self.validate_publish(intent)
        if errors:
            raise ValueError("invalid publish intent: " + "; ".join(errors))
        text = intent.content.get("text")
        if not isinstance(text, str) or not text:
            raise ValueError("X publish requires content.text")
        return self._http.request("POST", "https://api.x.com/2/tweets", {"text": text})


class LinkedInConnector(SocialConnector):
    platform = "linkedin"

    def __init__(self, token: str | None = None, *, api_version: str | None = None) -> None:
        self._http = BearerHTTPClient(token or os.environ.get("OIS_LINKEDIN_ACCESS_TOKEN", ""))
        self._api_version = api_version or os.environ.get("OIS_LINKEDIN_VERSION", "202604")

    def capabilities(self) -> set[str]:
        return {"publish", "read_events"}

    def normalize_event(self, payload: Mapping[str, Any]) -> SocialEvent:
        return SocialEvent(
            platform="linkedin",
            event_type="post",
            occurred_at=datetime.now(UTC),
            external_id=str(payload.get("id")) if payload.get("id") else None,
            text=payload.get("commentary"),
            raw=dict(payload),
        )

    def publish(self, intent: PublishIntent) -> dict[str, Any]:
        errors = self.validate_publish(intent)
        if errors:
            raise ValueError("invalid publish intent: " + "; ".join(errors))
        author = intent.account_ref
        commentary = intent.content.get("text")
        if not isinstance(commentary, str) or not commentary:
            raise ValueError("LinkedIn publish requires content.text")
        payload = {
            "author": author,
            "commentary": commentary,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        return self._http.request(
            "POST",
            "https://api.linkedin.com/rest/posts",
            payload,
            {"Linkedin-Version": self._api_version, "X-Restli-Protocol-Version": "2.0.0"},
        )


class InstagramGraphConnector(SocialConnector):
    platform = "instagram"

    def __init__(self, token: str | None = None, *, graph_version: str | None = None) -> None:
        self._http = BearerHTTPClient(token or os.environ.get("OIS_META_ACCESS_TOKEN", ""))
        self._version = graph_version or os.environ.get("OIS_META_GRAPH_VERSION", "v23.0")

    def capabilities(self) -> set[str]:
        return {"publish"}

    def normalize_event(self, payload: Mapping[str, Any]) -> SocialEvent:
        return SocialEvent(
            platform="instagram",
            event_type="media",
            occurred_at=datetime.now(UTC),
            external_id=str(payload.get("id")) if payload.get("id") else None,
            text=payload.get("caption"),
            raw=dict(payload),
        )

    def publish(self, intent: PublishIntent) -> dict[str, Any]:
        errors = self.validate_publish(intent)
        if errors:
            raise ValueError("invalid publish intent: " + "; ".join(errors))
        image_url = intent.content.get("image_url")
        if not isinstance(image_url, str) or not image_url:
            raise ValueError("Instagram publish requires content.image_url")
        base = f"https://graph.facebook.com/{self._version}/{quote(intent.account_ref, safe='')}"
        creation = self._http.request(
            "POST",
            f"{base}/media",
            {"image_url": image_url, "caption": intent.content.get("caption", "")},
        )
        creation_id = creation.get("id")
        if not creation_id:
            raise SocialAPIError("Instagram media creation returned no container id")
        return self._http.request("POST", f"{base}/media_publish", {"creation_id": creation_id})

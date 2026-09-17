"""Distribution boundary for Postiz and future platform adapters."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .connectors import AuthorizationRequiredError
from .contracts import ContentPackage


@dataclass(frozen=True)
class DistributionResult:
    status: str
    provider: str
    response: str = ""


class PostizDistributor:
    """Optional Postiz HTTP boundary; defaults to draft mode and requires authorization."""

    provider = "postiz"

    def __init__(self, endpoint: str | None = None, api_key: str | None = None) -> None:
        self.endpoint = endpoint or os.getenv("POSTIZ_WEBHOOK_URL")
        self.api_key = api_key or os.getenv("POSTIZ_API_KEY")

    def enqueue(self, package: ContentPackage, *, authorized: bool = False) -> DistributionResult:
        if not authorized:
            raise AuthorizationRequiredError("Postiz distribution requires explicit OIS authorization")
        if not self.endpoint:
            return DistributionResult("not_configured", self.provider)
        if not self.endpoint.startswith("https://") and not self.endpoint.startswith("http://localhost"):
            raise ValueError("Postiz endpoint must be HTTPS unless it is local development")

        payload: Mapping[str, object] = {
            "title": f"OIS campaign: {package.request.topic[:80]}",
            "content": {
                variant.platform.value: {
                    "hook": variant.hook,
                    "body": variant.body,
                    "cta": variant.cta,
                    "keywords": variant.keywords,
                    "hashtags": variant.hashtags,
                    "visual_prompts": variant.visual_prompts,
                }
                for variant in package.variants
            },
            "platforms": [platform.value for platform in package.request.platforms],
            "settings": {"scheduleType": "draft", "publishImmediately": False},
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(self.endpoint, data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=15) as response:
                body = response.read().decode(errors="replace")
                return DistributionResult("enqueued", self.provider, body[:2000])
        except Exception as exc:
            return DistributionResult("failed", self.provider, str(exc))

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol
from urllib.request import Request, urlopen

from .models import SourceDocument, WebIntelligenceRequest


class AcquisitionError(RuntimeError):
    """An acquisition engine could not obtain a source."""


class AcquisitionEngine(Protocol):
    name: str

    def can_handle(self, request: WebIntelligenceRequest) -> bool:
        ...

    def acquire(self, request: WebIntelligenceRequest) -> SourceDocument:
        ...


@dataclass
class HttpAcquisitionEngine:
    """Minimal standard-library HTTP engine.

    Production browser, proxy, CAPTCHA, and anti-bot providers are injected as
    separate engines. This engine deliberately has no hidden network bypasses.
    """

    timeout_seconds: float = 20.0
    user_agent: str = "OIS-WebIntelligence/0.1"
    name: str = "http"

    def can_handle(self, request: WebIntelligenceRequest) -> bool:
        return request.url.startswith(("http://", "https://")) and not request.javascript_required

    def acquire(self, request: WebIntelligenceRequest) -> SourceDocument:
        req = Request(request.url, headers={"User-Agent": self.user_agent})
        try:
            with urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
                return SourceDocument(
                    url=request.url,
                    status_code=getattr(response, "status", 200),
                    content_type=response.headers.get_content_type(),
                    body=body,
                    engine=self.name,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                    metadata={"headers": dict(response.headers.items())},
                )
        except Exception as exc:  # network libraries vary in their exception types
            raise AcquisitionError(str(exc)) from exc

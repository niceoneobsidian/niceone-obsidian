from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.request import Request, urlopen

from .models import SourceDocument, WebIntelligenceRequest


class AcquisitionEngine(Protocol):
    name: str

    def can_handle(self, request: WebIntelligenceRequest) -> bool: ...

    def acquire(self, request: WebIntelligenceRequest) -> SourceDocument: ...


@dataclass(frozen=True)
class HttpAcquisitionEngine:
    timeout_seconds: float = 10.0
    max_bytes: int = 2_000_000
    user_agent: str = "OIS-WebIntelligence/0.1"
    name: str = "http"

    def can_handle(self, request: WebIntelligenceRequest) -> bool:
        return request.url.startswith(("http://", "https://")) and not request.javascript_required

    def acquire(self, request: WebIntelligenceRequest) -> SourceDocument:
        http_request = Request(request.url, headers={"User-Agent": self.user_agent})
        with urlopen(http_request, timeout=self.timeout_seconds) as response:
            body = response.read(self.max_bytes + 1)
            if len(body) > self.max_bytes:
                raise ValueError("response exceeds configured size limit")
            return SourceDocument(
                url=request.url,
                status_code=int(getattr(response, "status", 200)),
                content_type=response.headers.get_content_type(),
                body=body.decode("utf-8", errors="replace"),
                engine=self.name,
                metadata={"content_length": len(body)},
            )

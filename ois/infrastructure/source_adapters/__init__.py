"""Governed live-source adapters built on the OIS Source Gateway."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import (
    AdapterHealth,
    AdapterResult,
    SourceAdapter,
    SourceAdapterRegistry,
)
from .database import DatabaseSourceAdapter
from .file import FileSourceAdapter
from .github import GitHubSourceAdapter
from .http import HttpSourceAdapter
from .polling import PollingSourceAdapter, PollPage
from .polling_engine import PollingEngine, PollingJob, PollingRun
from .rss import RSSSourceAdapter
from .sportmonks import SportmonksFootballAdapter, SportmonksQuery
from .webhook import WebhookVerifier

if TYPE_CHECKING:
    from .webhook_gateway import WebhookGateway, WebhookRequest

__all__ = [
    "AdapterHealth",
    "AdapterResult",
    "DatabaseSourceAdapter",
    "FileSourceAdapter",
    "GitHubSourceAdapter",
    "HttpSourceAdapter",
    "SportmonksFootballAdapter",
    "SportmonksQuery",
    "PollPage",
    "PollingEngine",
    "PollingJob",
    "PollingRun",
    "PollingSourceAdapter",
    "RSSSourceAdapter",
    "SourceAdapter",
    "SourceAdapterRegistry",
    "WebhookGateway",
    "WebhookRequest",
    "WebhookVerifier",
]


def __getattr__(name: str) -> Any:
    """Load webhook gateway exports lazily to avoid source-gateway import cycles."""
    if name in {"WebhookGateway", "WebhookRequest"}:
        from .webhook_gateway import WebhookGateway, WebhookRequest

        return {"WebhookGateway": WebhookGateway, "WebhookRequest": WebhookRequest}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Governed live-source adapters built on the OIS Source Gateway."""

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
from .webhook import WebhookVerifier
from .webhook_gateway import WebhookGateway, WebhookRequest

__all__ = [
    "AdapterHealth",
    "AdapterResult",
    "DatabaseSourceAdapter",
    "FileSourceAdapter",
    "GitHubSourceAdapter",
    "HttpSourceAdapter",
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

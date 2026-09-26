"""Governed live-source adapters built on the OIS Source Gateway."""

from ois.infrastructure.source_adapters.base import (
    AdapterHealth,
    AdapterResult,
    SourceAdapter,
    SourceAdapterRegistry,
)
from ois.infrastructure.source_adapters.database import DatabaseSourceAdapter
from ois.infrastructure.source_adapters.file import FileSourceAdapter
from ois.infrastructure.source_adapters.github import GitHubSourceAdapter
from ois.infrastructure.source_adapters.http import HttpSourceAdapter
from ois.infrastructure.source_adapters.polling import PollPage, PollingSourceAdapter
from ois.infrastructure.source_adapters.rss import RSSSourceAdapter
from ois.infrastructure.source_adapters.webhook import WebhookVerifier

__all__ = [
    "AdapterHealth",
    "AdapterResult",
    "DatabaseSourceAdapter",
    "FileSourceAdapter",
    "GitHubSourceAdapter",
    "HttpSourceAdapter",
    "PollPage",
    "PollingSourceAdapter",
    "RSSSourceAdapter",
    "SourceAdapter",
    "SourceAdapterRegistry",
    "WebhookVerifier",
]

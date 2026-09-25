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
from .polling import PollingSourceAdapter
from .rss import RSSSourceAdapter
from .webhook import WebhookVerifier

__all__ = [
    "AdapterHealth",
    "AdapterResult",
    "DatabaseSourceAdapter",
    "FileSourceAdapter",
    "GitHubSourceAdapter",
    "HttpSourceAdapter",
    "PollingSourceAdapter",
    "RSSSourceAdapter",
    "SourceAdapter",
    "SourceAdapterRegistry",
    "WebhookVerifier",
]

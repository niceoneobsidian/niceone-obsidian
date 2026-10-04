"""GitHub source integration."""

from .oauth import build_github_oauth
from .source import GitHubSource

__all__ = ["GitHubSource", "build_github_oauth"]

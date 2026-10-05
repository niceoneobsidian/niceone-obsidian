"""GitHub source integration."""

from .app_auth import GitHubAppAuthenticator, GitHubAppConfig
from .oauth import build_github_oauth
from .source import GitHubSource

__all__ = [
    "GitHubAppAuthenticator",
    "GitHubAppConfig",
    "GitHubSource",
    "build_github_oauth",
]

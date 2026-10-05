"""GitHub source integration."""

from .app_auth import GitHubAppAuthenticator, GitHubAppConfig\nfrom .oauth import build_github_oauth
from .source import GitHubSource

__all__ = [\n    "GitHubAppAuthenticator",\n    "GitHubAppConfig",\n    "GitHubSource",\n    "build_github_oauth",\n]

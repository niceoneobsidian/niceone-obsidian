"""YouTube API integration primitives for OIS.

The implementation adapts the official youtube/api-samples request/resource
patterns into typed, provider-boundary code. Runtime credentials are supplied
by OIS secret management; no credentials are stored here.
"""

from .client import YouTubeClient, YouTubeOAuthConfig
from .models import YouTubeChannel, YouTubeVideo, YouTubeSearchResult

__all__ = [
    "YouTubeClient",
    "YouTubeOAuthConfig",
    "YouTubeChannel",
    "YouTubeVideo",
    "YouTubeSearchResult",
]

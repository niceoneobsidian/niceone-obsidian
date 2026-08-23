"""OIS capability implementations and registration helpers."""

from typing import Any

from .tiktok_growth import TikTokContentAgent


def register_tiktok_capabilities(registry: Any) -> TikTokContentAgent:
    """Register the approved TikTok acquisition capability in an OIS registry."""
    agent = TikTokContentAgent()
    registry.register(agent)
    return agent


__all__ = ["TikTokContentAgent", "register_tiktok_capabilities"]

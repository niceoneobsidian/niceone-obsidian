"""OIS capability implementations and registration helpers."""

from .tiktok_growth import TikTokContentAgent


def register_tiktok_capabilities(registry: object) -> TikTokContentAgent:
    """Register the approved TikTok acquisition capability in an OIS registry."""
    agent = TikTokContentAgent()
    registry.register(agent)  # type: ignore[attr-defined]
    return agent


__all__ = ["TikTokContentAgent", "register_tiktok_capabilities"]

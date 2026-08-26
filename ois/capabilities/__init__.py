"""OIS capability implementations and registration helpers."""

from typing import Any

from ..events.ingestion import EventIngestion
from ..events.store import EventStore
from .tiktok_growth import TikTokContentAgent


def register_tiktok_capabilities(registry: Any) -> TikTokContentAgent:
    """Register the approved TikTok acquisition capability in an OIS registry."""
    agent = TikTokContentAgent()
    registry.register(agent)
    return agent


def register_event_ingestion(registry: Any, store: EventStore) -> EventIngestion:
    """Register the canonical event perception capability."""
    capability = EventIngestion(store)
    registry.register(capability)
    return capability


__all__ = [
    "EventIngestion",
    "TikTokContentAgent",
    "register_event_ingestion",
    "register_tiktok_capabilities",
]

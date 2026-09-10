"""StatsBomb Open Data adapter for historical model training.

StatsBomb Open Data is treated as a historical/event-data source, not a live
provider. It complements live commercial feeds without being used as a source
of current odds or current match state.
"""

from __future__ import annotations

from typing import Any

from .feeds import FeedError, FeedObservation, Transport, default_transport, payload_hash


class StatsBombOpenDataProvider:
    """Read public StatsBomb competition, match and event archives."""

    provider_name = "statsbomb-open-data"
    base_url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

    def __init__(self, transport: Transport = default_transport) -> None:
        self.transport = transport

    def competitions(self) -> FeedObservation:
        return self._get("/competitions.json")

    def matches(self, competition_id: int, season_id: int) -> FeedObservation:
        return self._get(f"/matches/{competition_id}/{season_id}.json")

    def events(self, match_id: int) -> FeedObservation:
        return self._get(f"/events/{match_id}.json")

    def shot_events(self, match_id: int) -> tuple[dict[str, Any], ...]:
        observation = self.events(match_id)
        events = observation.payload.get("events")
        if not isinstance(events, list):
            raise FeedError("StatsBomb event archive has an unexpected structure")
        return tuple(
            event for event in events if isinstance(event, dict) and event.get("type", {}).get("name") == "Shot"
        )

    def _get(self, resource: str) -> FeedObservation:
        response = self.transport(f"{self.base_url}{resource}", {}, {})
        if response.status < 200 or response.status >= 300:
            raise FeedError(f"StatsBomb Open Data HTTP status {response.status}")
        return FeedObservation(
            provider=self.provider_name,
            resource=f"{self.base_url}{resource}",
            payload_sha256=payload_hash(response.payload),
            payload=response.payload,
        )

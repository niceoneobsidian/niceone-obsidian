"""StatsBomb Open Data adapter for historical model training.

StatsBomb Open Data is treated as a historical/event-data source, not a live
provider. It complements live commercial feeds without being used as a source
of current odds or current match state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from .feeds import FeedError


class StatsBombObservation(BaseModel):
    """Auditable StatsBomb archive response; payload may be a list or object."""

    model_config = ConfigDict(extra="forbid")

    provider: str = "statsbomb-open-data"
    resource: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload_sha256: str
    payload: Any


class StatsBombOpenDataProvider:
    """Read public StatsBomb competition, match and event archives."""

    provider_name = "statsbomb-open-data"
    base_url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

    def competitions(self) -> StatsBombObservation:
        return self._get("/competitions.json")

    def matches(self, competition_id: int, season_id: int) -> StatsBombObservation:
        return self._get(f"/matches/{competition_id}/{season_id}.json")

    def events(self, match_id: int) -> StatsBombObservation:
        return self._get(f"/events/{match_id}.json")

    def shot_events(self, match_id: int) -> tuple[dict[str, Any], ...]:
        observation = self.events(match_id)
        if not isinstance(observation.payload, list):
            raise FeedError("StatsBomb event archive has an unexpected structure")
        return tuple(
            event
            for event in observation.payload
            if isinstance(event, dict)
            and isinstance(event.get("type"), dict)
            and event["type"].get("name") == "Shot"
        )

    def _get(self, resource: str) -> StatsBombObservation:
        url = f"{self.base_url}{resource}"
        request = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise FeedError(f"StatsBomb Open Data HTTP status {exc.code}") from exc
        except URLError as exc:
            raise FeedError(f"StatsBomb Open Data request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise FeedError("StatsBomb Open Data returned invalid JSON") from exc

        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return StatsBombObservation(
            resource=url,
            payload_sha256=hashlib.sha256(encoded).hexdigest(),
            payload=payload,
        )

"""Observed bookmaker market coverage derived from normalized odds evidence.

Coverage is evidence-driven: a market is reported as available only when it has
actually appeared in the supplied provider observations. The catalog is a
canonical taxonomy, not a claim that every bookmaker offers every market.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .web_sources import OddsObservation


class BookmakerMarketCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bookmaker: str
    provider: str
    match_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    market_keys: tuple[str, ...] = ()
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None


def build_market_coverage(observations: list[OddsObservation]) -> list[BookmakerMarketCoverage]:
    """Build deterministic bookmaker coverage from observed odds records."""
    groups: dict[tuple[str, str], list[OddsObservation]] = defaultdict(list)
    for observation in observations:
        groups[(observation.provider, observation.bookmaker)].append(observation)

    result: list[BookmakerMarketCoverage] = []
    for (provider, bookmaker), records in sorted(groups.items()):
        market_keys = sorted({
            record.canonical_market_key
            for record in records
            if record.canonical_market_key is not None
        })
        timestamps = [record.observed_at for record in records]
        result.append(
            BookmakerMarketCoverage(
                bookmaker=bookmaker,
                provider=provider,
                match_count=len({record.match_id for record in records}),
                observation_count=len(records),
                market_keys=tuple(market_keys),
                first_observed_at=min(timestamps),
                last_observed_at=max(timestamps),
            )
        )
    return result

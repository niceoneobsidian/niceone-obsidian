"""Integration boundary between Football Intelligence and OIS platform services."""

from __future__ import annotations

from typing import Any

from .ensemble import FootballEnsemble
from .registry import manifest
from .schemas import FootballPrediction, MatchState

DOMAIN_ID = "football_intelligence"


def domain_manifest() -> dict[str, Any]:
    """Return declarative registration data; platform registries remain authoritative."""
    return manifest()


def predict_match(match: MatchState, ensemble: FootballEnsemble | None = None) -> FootballPrediction:
    """Pure prediction entrypoint suitable for a governed OIS capability adapter."""
    return (ensemble or FootballEnsemble()).predict(match)

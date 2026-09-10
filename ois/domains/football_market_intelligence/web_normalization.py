"""Normalization, provenance and temporal-integrity rules for web observations."""

from __future__ import annotations

from datetime import UTC, datetime
from time import monotonic

from .web_sources import (
    MatchObservation,
    NormalizationResult,
    OddsObservation,
    ProviderHealth,
    WebObservation,
    WebSource,
    WebTransport,
)


def normalize_observations(
    source: WebSource,
    observations: list[WebObservation],
    *,
    prediction_created_at: datetime | None = None,
) -> NormalizationResult:
    """Apply source identity and leakage-safe temporal validation."""
    warnings: list[str] = []
    records: list[MatchObservation | OddsObservation] = []
    rejected = 0
    for observation in observations:
        if observation.source_id != source.source_id:
            rejected += 1
            warnings.append(f"rejected source mismatch: {observation.observation_id}")
            continue
        if prediction_created_at is not None and observation.source_timestamp is not None:
            if observation.source_timestamp > prediction_created_at:
                rejected += 1
                warnings.append(
                    f"rejected future observation: {observation.observation_id} "
                    f"source={observation.source_timestamp.isoformat()} "
                    f"prediction={prediction_created_at.isoformat()}"
                )
                continue
        records.append(observation)
    return NormalizationResult(
        source_id=source.source_id,
        records=records,
        warnings=warnings,
        rejected_count=rejected,
    )


def check_provider_health(
    source: WebSource,
    uri: str,
    transport: WebTransport,
    *,
    headers: dict[str, str] | None = None,
) -> ProviderHealth:
    """Perform a minimal provider request without interpreting business data."""
    checked_at = datetime.now(UTC)
    started = monotonic()
    try:
        transport(uri, headers or {})
    except Exception as exc:
        return ProviderHealth(
            provider=source.provider,
            checked_at=checked_at,
            available=False,
            latency_ms=(monotonic() - started) * 1000,
            error_class=type(exc).__name__,
        )
    return ProviderHealth(
        provider=source.provider,
        checked_at=checked_at,
        available=True,
        latency_ms=(monotonic() - started) * 1000,
    )


def assert_temporal_integrity(
    observations: list[WebObservation], prediction_created_at: datetime
) -> None:
    """Fail closed if a prediction would consume future-dated source evidence."""
    future = [
        observation.observation_id
        for observation in observations
        if observation.source_timestamp is not None
        and observation.source_timestamp > prediction_created_at
    ]
    if future:
        raise ValueError(f"future-dated observations are not prediction-safe: {future}")

"""Contracts for governed live-source integrations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from math import isfinite
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_SENSITIVE_PROVENANCE_KEYS = {
    "authorization",
    "cookie",
    "set_cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_token",
    "bearer_token",
    "api_key",
    "private_key",
    "credential",
    "credentials",
}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in _SENSITIVE_PROVENANCE_KEYS or normalized.endswith(
        ("_secret", "_password", "_token", "_api_key")
    )


def _safe_provenance_value(value: Any) -> Any:
    """Copy provenance metadata while redacting credential-like fields recursively."""
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            safe[str(key)] = "[REDACTED]" if _is_sensitive_key(str(key)) else (
                _safe_provenance_value(item)
            )
        return safe
    if isinstance(value, (list, tuple)):
        return [_safe_provenance_value(item) for item in value]
    return value


def _safe_endpoint(endpoint: str) -> str:
    """Remove credential-like query values from endpoint URLs before recording provenance."""
    parts = urlsplit(endpoint)
    query = [
        (key, "[REDACTED]" if _is_sensitive_key(key) else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@dataclass(frozen=True)
class FreshnessPolicy:
    """Maximum age accepted for a source observation."""

    max_age_seconds: float

    def __post_init__(self) -> None:
        if not isfinite(self.max_age_seconds) or self.max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be finite and positive")

    def is_fresh(self, observed_at: datetime, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        return current - observed_at <= timedelta(seconds=self.max_age_seconds)

    def expires_at(self, observed_at: datetime) -> datetime:
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        return observed_at + timedelta(seconds=self.max_age_seconds)


@dataclass(frozen=True)
class SourceProvenance:
    """Stable, secret-redacted provenance attached to a source observation."""

    provider: str
    endpoint: str
    operation: str
    request_id: str
    resource_id: str = ""
    cursor: str | None = None
    observed_at: datetime | None = None
    metadata: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        observed = self.observed_at or datetime.now(UTC)
        return {
            "provider": self.provider,
            "endpoint": _safe_endpoint(self.endpoint),
            "operation": self.operation,
            "request_id": self.request_id,
            "resource_id": self.resource_id,
            "cursor": self.cursor,
            "observed_at": observed.isoformat(),
            "metadata": _safe_provenance_value(self.metadata or {}),
        }


@dataclass(frozen=True)
class SourceSpec:
    """Registry metadata describing a source without embedding provider secrets."""

    source_id: str
    provider: str
    protocol: str
    version: str = "v1"
    freshness: FreshnessPolicy | None = None
    capabilities: tuple[str, ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.source_id or not self.provider or not self.protocol:
            raise ValueError("source_id, provider, and protocol are required")

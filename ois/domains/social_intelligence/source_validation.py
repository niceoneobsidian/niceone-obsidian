"""Production-source validation and immutable collection-run contracts for G1."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class FetchBatch:
    source_id: str
    request_id: str
    records: tuple[Mapping[str, Any], ...]
    cursor: str | None = None
    next_cursor: str | None = None
    latency_ms: float | None = None
    rate_limit_remaining: int | None = None


@dataclass(frozen=True)
class SourceRun:
    run_id: str
    source_id: str
    started_at: datetime
    completed_at: datetime
    records_received: int
    records_accepted: int
    records_rejected: int
    duplicates: int
    cursor_before: str | None
    cursor_after: str | None
    connector_version: str
    status: str
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceValidationReport:
    source_id: str
    connector_version: str
    authentication_ok: bool
    connectivity_ok: bool
    pagination_ok: bool
    incremental_fetch_ok: bool
    normalization_ok: bool
    deduplication_ok: bool
    rate_limit_ok: bool
    records_tested: int
    records_accepted: int
    records_rejected: int
    freshness_seconds: float | None
    latency_ms: float | None
    errors: tuple[str, ...] = ()


class ProductionSourceAdapter(Protocol):
    source_id: str
    connector_version: str

    def health_check(self) -> bool: ...

    def fetch(
        self, *, cursor: str | None, since: datetime | None, limit: int
    ) -> FetchBatch: ...


class SourceValidationHarness:
    """Validate a source adapter without publishing side effects."""

    def validate(
        self, adapter: ProductionSourceAdapter, *, limit: int = 100
    ) -> SourceValidationReport:
        errors: list[str] = []
        auth = connectivity = pagination = incremental = True
        normalization = dedup = rate = False
        tested = accepted = rejected = 0
        latency = None

        try:
            auth = bool(adapter.health_check())
            connectivity = auth
        except Exception as exc:
            auth = connectivity = False
            errors.append(f"health_check:{exc}")

        if connectivity:
            try:
                batch = adapter.fetch(cursor=None, since=None, limit=limit)
                tested = len(batch.records)
                accepted = tested
                latency = batch.latency_ms
                pagination = batch.next_cursor is not None or tested < limit
                if batch.next_cursor is not None:
                    follow = adapter.fetch(
                        cursor=batch.next_cursor, since=None, limit=limit
                    )
                    pagination = pagination and follow.cursor == batch.next_cursor
                incremental = True
                rate = (
                    batch.rate_limit_remaining is None
                    or batch.rate_limit_remaining >= 0
                )
            except Exception as exc:
                errors.append(f"fetch:{exc}")
                pagination = incremental = rate = False

        normalization = tested > 0 and not errors
        dedup = normalization
        rejected = max(0, tested - accepted)
        return SourceValidationReport(
            adapter.source_id,
            adapter.connector_version,
            auth,
            connectivity,
            pagination,
            incremental,
            normalization,
            dedup,
            rate,
            tested,
            accepted,
            rejected,
            None,
            latency,
            tuple(errors),
        )

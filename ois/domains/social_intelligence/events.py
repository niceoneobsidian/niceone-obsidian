"""Canonical source events entering the OIS intelligence plane."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CanonicalSourceEvent(BaseModel):
    """Provider-neutral event contract for intelligence ingestion."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    tenant_id: str
    workspace_id: str
    source_id: str
    source_record_id: str
    event_type: str
    payload: dict[str, Any]
    payload_hash: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    schema_version: str = "source.event.v1"
    connector_version: str = "v1"
    metadata: dict[str, Any] = Field(default_factory=dict)

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_ref: str
    source_kind: str
    observed_at: datetime
    collector: str
    sequence: int | None = None
    raw_content_hash: str | None = None


class EventValidation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    contract_version: str = "1.0"
    validated_at: datetime
    validator: str
    errors: tuple[str, ...] = ()


class Event(BaseModel):
    """Canonical, immutable OIS observation crossing the perception boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    source: str = Field(min_length=1)
    tenant: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    provenance: EventProvenance
    correlation_id: UUID | None = None
    execution_id: UUID | None = None
    policy_context: dict[str, Any] = Field(default_factory=dict)
    validation: EventValidation
    content_hash: str = ""

    @field_validator("timestamp", mode="after")
    @classmethod
    def timestamp_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    def canonical_payload(self) -> dict[str, Any]:
        data = self.model_dump(mode="json", exclude={"content_hash"})
        return data

    def compute_hash(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def with_content_hash(self) -> Event:
        digest = self.compute_hash()
        return self.model_copy(update={"content_hash": digest})

    def assert_integrity(self) -> None:
        if not self.content_hash or self.content_hash != self.compute_hash():
            raise ValueError(f"event integrity check failed: {self.event_id}")

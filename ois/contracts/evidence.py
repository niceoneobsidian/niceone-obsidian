"""Durable evidence contract, distinct from logs and traces."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EvidenceKind(StrEnum):
    EXECUTION = "execution"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    RECOVERY = "recovery"


class EvidenceRecord(BaseModel):
    """Append-oriented record proving a governed lifecycle event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID
    kind: EvidenceKind
    capability_id: str = Field(min_length=1)
    capability_version: str = Field(min_length=1)
    contract_version: str = "1.0"
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: dict[str, Any] = Field(default_factory=dict)

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class PlatformIdentity:
    tenant_id: str
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    workflow_id: str | None = None
    agent_id: str | None = None
    capability_id: str | None = None
    tool_id: str | None = None
    model_id: str | None = None


@dataclass(frozen=True)
class Lineage:
    artifact_id: str
    parent_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Measurement:
    name: str
    value: float
    unit: str
    recorded_at: datetime = field(default_factory=utc_now)
    dimensions: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class QualityGate:
    name: str
    passed: bool
    reason: str = ""


@dataclass(frozen=True)
class VersionRef:
    component: str
    version: str
    commit: str | None = None

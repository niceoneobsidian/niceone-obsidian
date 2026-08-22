from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class WebIntelligenceRequest:
    url: str
    objective: str = "extract"
    extract_schema: Mapping[str, Any] = field(default_factory=dict)
    preferred_engine: str | None = None
    javascript_required: bool = False


@dataclass(frozen=True)
class SourceDocument:
    url: str
    status_code: int
    content_type: str
    body: str
    engine: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WebIntelligenceResult:
    success: bool
    source: SourceDocument | None
    extracted: Mapping[str, Any] | None
    evidence: Mapping[str, Any] | None
    engine: str | None
    attempts: int
    errors: tuple[str, ...] = ()

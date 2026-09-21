"""Provider-agnostic multimodal media ingestion and analysis contracts for G2."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from .intelligence import ContentGenome, ModalityObservation, build_content_genome

@dataclass(frozen=True)
class ContentAsset:
    content_id: str
    media_type: str
    source_uri: str
    published_at: datetime | None = None
    duration_seconds: float | None = None
    metadata: dict[str, Any] | None = None

class MultimodalAnalyzer(Protocol):
    def analyze(self, asset: ContentAsset) -> tuple[ModalityObservation, ...]: ...

class DeterministicMediaAnalyzer:
    """Reference analyzer for integration tests; production providers implement the same protocol."""
    def analyze(self, asset: ContentAsset) -> tuple[ModalityObservation, ...]:
        return (ModalityObservation("text", {"hook":{"strength":0.0},"narrative":{},
            "emotion":{},"audience_signals":{},"brand_signals":{}},
            source_ref=asset.source_uri, confidence=0.0),)

class MediaPipeline:
    def __init__(self, analyzer: MultimodalAnalyzer) -> None: self._analyzer=analyzer
    def process(self, asset: ContentAsset) -> ContentGenome:
        return build_content_genome(content_id=asset.content_id,
            observations=list(self._analyzer.analyze(asset)))

"""M14 Content Intelligence primitives for the Social Intelligence Fabric.

The module is deliberately model-provider agnostic. It converts already extracted
multimodal observations into a stable, versioned Content Genome that downstream
prediction, experimentation, measurement, and learning components can consume.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class ModalityObservation:
    """Normalized evidence extracted from one media modality."""

    modality: str
    features: Mapping[str, Any]
    source_ref: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class ContentGenome:
    """Structured creative representation used by M15-M17."""

    content_id: str
    version: str
    topic: str | None
    hook: Mapping[str, Any]
    narrative: Mapping[str, Any]
    emotion: Mapping[str, Any]
    visual: Mapping[str, Any]
    audio: Mapping[str, Any]
    temporal: Mapping[str, Any]
    audience_signals: Mapping[str, Any]
    brand_signals: Mapping[str, Any]
    observations: tuple[ModalityObservation, ...] = field(default_factory=tuple)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "content_id": self.content_id,
            "version": self.version,
            "topic": self.topic,
            "hook": dict(self.hook),
            "narrative": dict(self.narrative),
            "emotion": dict(self.emotion),
            "visual": dict(self.visual),
            "audio": dict(self.audio),
            "temporal": dict(self.temporal),
            "audience_signals": dict(self.audience_signals),
            "brand_signals": dict(self.brand_signals),
            "observations": [
                {
                    "modality": item.modality,
                    "features": dict(item.features),
                    "source_ref": item.source_ref,
                    "confidence": item.confidence,
                }
                for item in self.observations
            ],
        }

    def fingerprint(self) -> str:
        """Return a deterministic fingerprint for provenance and caching."""
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        ).encode()
        return sha256(encoded).hexdigest()


def build_content_genome(
    *,
    content_id: str,
    observations: list[ModalityObservation],
    version: str = "m14.v1",
    topic: str | None = None,
) -> ContentGenome:
    """Build a deterministic genome from normalized multimodal observations.

    Missing modalities remain explicit instead of being hallucinated. This makes
    the object safe to pass to prediction and validation layers.
    """
    by_modality = {item.modality: item for item in observations}
    text = by_modality.get("text")
    image = by_modality.get("image")
    audio = by_modality.get("audio")
    video = by_modality.get("video")

    hook = dict((text.features if text else {}).get("hook", {}))
    visual = dict((image.features if image else {}).get("visual", {}))
    audio_features = dict((audio.features if audio else {}).get("audio", {}))
    temporal = dict((video.features if video else {}).get("temporal", {}))
    narrative = dict((text.features if text else {}).get("narrative", {}))
    emotion = dict((text.features if text else {}).get("emotion", {}))
    audience = dict((text.features if text else {}).get("audience_signals", {}))
    brand = dict((text.features if text else {}).get("brand_signals", {}))

    return ContentGenome(
        content_id=content_id,
        version=version,
        topic=topic,
        hook=hook,
        narrative=narrative,
        emotion=emotion,
        visual=visual,
        audio=audio_features,
        temporal=temporal,
        audience_signals=audience,
        brand_signals=brand,
        observations=tuple(observations),
    )

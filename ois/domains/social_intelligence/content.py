"""G2 content-ingestion and multimodal-analysis contracts.

The domain accepts real content records and normalized modality observations.
Provider-specific OCR, ASR, vision and video models implement the
MultimodalAnalyzer protocol; the deterministic analyzer is intentionally
limited to text/metadata so it never pretends to perform vision or audio
inference it cannot verify.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .intelligence import ContentGenome, ModalityObservation, build_content_genome


@dataclass(frozen=True)
class ContentInput:
    """Canonical input to G2 analysis."""

    content_id: str
    text: str | None = None
    transcript: str | None = None
    metadata: Mapping[str, Any] | None = None
    modality_payloads: Mapping[str, Mapping[str, Any]] | None = None


class MultimodalAnalyzer(Protocol):
    """Provider boundary for text, image, audio and video analysis."""

    def analyze(self, content: ContentInput) -> tuple[ModalityObservation, ...]: ...


class StructuredMultimodalAnalyzer:
    """Reference analyzer for already-normalized modality features.

    Production OCR, ASR, vision and video providers can implement the same
    protocol. The reference implementation never claims inference it cannot
    verify.
    """

    def analyze(self, content: ContentInput) -> tuple[ModalityObservation, ...]:
        observations: list[ModalityObservation] = []
        text = content.transcript or content.text
        if text:
            words = [word for word in text.split() if word]
            observations.append(
                ModalityObservation(
                    modality="text",
                    features={
                        "text": {"word_count": len(words)},
                        "hook": {"strength": min(1.0, len(words[:12]) / 12.0)},
                    },
                    source_ref=f"content:{content.content_id}",
                    confidence=1.0,
                )
            )

        for modality, features in (content.modality_payloads or {}).items():
            if modality not in {"text", "image", "audio", "video"}:
                raise ValueError(f"unsupported modality: {modality}")
            observations.append(
                ModalityObservation(
                    modality=modality,
                    features=dict(features),
                    source_ref=f"content:{content.content_id}",
                    confidence=1.0,
                )
            )
        return tuple(observations)


def analyze_content(
    content: ContentInput,
    *,
    analyzer: MultimodalAnalyzer,
    version: str = "m14.v1",
    topic: str | None = None,
) -> ContentGenome:
    """Run the provider boundary and build the deterministic Content Genome."""
    observations = analyzer.analyze(content)
    return build_content_genome(
        content_id=content.content_id,
        observations=list(observations),
        version=version,
        topic=topic,
    )

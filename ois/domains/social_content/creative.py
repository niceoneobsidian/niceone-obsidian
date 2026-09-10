"""Provider-neutral creative generation and validation helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .contracts import ContentObjectiveRequest, ContentVariant, Platform, ResearchEvidence


class CreativeProvider:
    """Wrap an LLM/agent provider without granting it publishing authority."""

    def __init__(self, generate: Callable[[str], dict[str, Any]]) -> None:
        self._generate = generate

    def generate(
        self,
        request: ContentObjectiveRequest,
        platform: Platform,
        evidence: list[ResearchEvidence],
    ) -> ContentVariant:
        prompt = build_creative_brief(request, platform, evidence)
        result = self._generate(prompt)
        return ContentVariant(
            platform=platform,
            hook=str(result.get("hook", "")),
            body=str(result.get("body", "")),
            cta=str(result.get("cta", "")),
            keywords=[str(x) for x in result.get("keywords", [])],
            hashtags=[str(x) for x in result.get("hashtags", [])],
            visual_prompts=[str(x) for x in result.get("visual_prompts", [])],
            evidence=evidence,
        )


def build_creative_brief(
    request: ContentObjectiveRequest,
    platform: Platform,
    evidence: list[ResearchEvidence],
) -> str:
    """Generate a structured, platform-native brief with provenance constraints."""

    sources = "\n".join(f"- {item.source_id}: {item.title} {item.url}" for item in evidence)
    return (
        "You are an OIS governed creative-content agent.\n"
        f"Topic: {request.topic}\nPlatform: {platform.value}\n"
        f"Audience: {request.audience}\nObjective: {request.objective.value}\n"
        f"Tone: {request.tone}\nBrand: {request.brand_context}\n"
        "Create a platform-native hook, body, CTA, keywords, hashtags and visual prompts. "
        "Do not invent factual claims. If evidence is insufficient, state that explicitly.\n"
        f"Evidence:\n{sources}"
    )


def validate_variant(variant: ContentVariant, *, require_evidence: bool) -> list[str]:
    """Return deterministic quality failures; publishing is never performed here."""

    errors: list[str] = []
    if not variant.hook.strip():
        errors.append("missing_hook")
    if not variant.body.strip():
        errors.append("missing_body")
    if require_evidence and not variant.evidence:
        errors.append("missing_evidence")
    if any(item.verification == "contested" for item in variant.evidence):
        errors.append("contested_evidence")
    return errors

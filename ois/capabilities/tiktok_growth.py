from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from ois.kernel.contracts import AgentContract, InvocationRequest, InvocationResult
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel


ACQUISITION_SOURCES: tuple[Mapping[str, Any], ...] = (
    {
        "id": "tiktok-viral-hooks",
        "url": "https://github.com/shixinzhang/tiktok-viral-hooks",
        "license": "CC-BY-NC-SA-4.0 (repository corpus); MIT (scripts, per repository documentation)",
        "acquisition_mode": "knowledge_reference_only",
        "commercial_corpus_use": False,
    },
    {
        "id": "captionaize",
        "url": "https://github.com/tjoab/captionaize",
        "license": "MIT",
        "acquisition_mode": "implementation_reference",
        "commercial_corpus_use": True,
    },
    {
        "id": "social-media-caption-generator-claude",
        "url": "https://github.com/rediumvex/social-media-caption-generator-claude",
        "license": "MIT",
        "acquisition_mode": "workflow_reference",
        "commercial_corpus_use": True,
    },
)


HOOK_PATTERNS: Mapping[str, str] = {
    "problem_first": "State the painful or costly problem immediately, then promise a concrete resolution.",
    "curiosity_gap": "Expose an unexpected result or contradiction, then explain the mechanism.",
    "mistake_correction": "Name a common mistake, explain why it fails, and replace it with a better action.",
    "specific_outcome": "Lead with a measurable or observable outcome, then show the path to reproduce it.",
    "step_by_step": "Promise a bounded number of useful steps and execute them without filler.",
    "contrarian": "Challenge a widely held assumption, but support the alternative with evidence or reasoning.",
}


@dataclass(frozen=True)
class TikTokContentBrief:
    topic: str
    audience: str = ""
    objective: str = "education"
    source_text: str = ""
    tone: str = "clear"
    desired_length_seconds: int = 30


@dataclass(frozen=True)
class TikTokContentPlan:
    topic: str
    hook: str
    hook_pattern: str
    caption: str
    keywords: tuple[str, ...]
    hashtags: tuple[str, ...]
    cta: str
    quality_checks: tuple[str, ...]
    provenance: tuple[Mapping[str, Any], ...]


def _keywords(topic: str) -> tuple[str, ...]:
    words = [w.strip(".,!?;:#()[]{}") for w in topic.lower().split()]
    return tuple(dict.fromkeys(w for w in words if len(w) > 2))[:5]


def _select_pattern(brief: TikTokContentBrief) -> str:
    text = f"{brief.topic} {brief.source_text}".lower()
    if any(token in text for token in ("mistake", "wrong", "avoid", "stop")):
        return "mistake_correction"
    if any(token in text for token in ("how", "steps", "guide", "tutorial")):
        return "step_by_step"
    if any(token in text for token in ("result", "increase", "reduce", "growth")):
        return "specific_outcome"
    return "problem_first"


def build_tiktok_plan(brief: TikTokContentBrief) -> TikTokContentPlan:
    """Create an OIS-native TikTok plan without importing third-party corpus text."""
    if not brief.topic.strip():
        raise ValueError("topic is required")

    pattern = _select_pattern(brief)
    keywords = _keywords(brief.topic)
    keyword_phrase = ", ".join(keywords) if keywords else brief.topic

    hook_templates = {
        "problem_first": f"If you are struggling with {brief.topic}, start here.",
        "curiosity_gap": f"Most people misunderstand {brief.topic}. Here is what actually matters.",
        "mistake_correction": f"The biggest mistake with {brief.topic} is doing this first.",
        "specific_outcome": f"Here is a practical way to improve {brief.topic} without adding complexity.",
        "step_by_step": f"Here are the essential steps for {brief.topic}.",
        "contrarian": f"The usual advice about {brief.topic} misses one important point.",
    }
    hook = hook_templates[pattern]
    caption = f"{hook} Focus: {keyword_phrase}. Save this as a reference and test one change at a time."
    cta = "Save this for later and comment with the result you want to improve."
    checks = (
        "single_clear_topic",
        "hook_delivers_immediate_context",
        "caption_matches_spoken_content",
        "keywords_are_natural",
        "hashtags_are_specific_and_limited",
        "no_watermark_or_reposted_source_required",
        "no_claim_of_guaranteed_virality",
    )
    provenance = tuple(ACQUISITION_SOURCES)

    return TikTokContentPlan(
        topic=brief.topic,
        hook=hook,
        hook_pattern=pattern,
        caption=caption,
        keywords=keywords,
        hashtags=tuple(f"#{k}" for k in keywords[:3]),
        cta=cta,
        quality_checks=checks,
        provenance=provenance,
    )


class TikTokContentAgent:
    """OIS agent that turns a content brief into a validated TikTok plan."""

    contract = AgentContract(
        capability_id="tiktok.content.plan",
        version="1.0.0",
        description="Create an OIS-native TikTok hook, caption, SEO and CTA plan.",
        input_schema={
            "type": "object",
            "required": ["topic"],
            "properties": {
                "topic": {"type": "string"},
                "audience": {"type": "string"},
                "objective": {"type": "string"},
                "source_text": {"type": "string"},
                "tone": {"type": "string"},
                "desired_length_seconds": {"type": "integer"},
            },
        },
        output_schema={
            "type": "object",
            "required": ["hook", "caption", "keywords", "hashtags", "cta"],
        },
        risk_level=RiskLevel.LOW,
        permissions=(),
        allowed_domains=(),
        timeout_seconds=10.0,
        max_retries=0,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
        required_tools=(),
        model_requirements={"external_model": False},
        max_iterations=1,
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        started = datetime.now(timezone.utc).isoformat()
        try:
            data = request.input
            brief = TikTokContentBrief(
                topic=str(data.get("topic", "")),
                audience=str(data.get("audience", "")),
                objective=str(data.get("objective", "education")),
                source_text=str(data.get("source_text", "")),
                tone=str(data.get("tone", "clear")),
                desired_length_seconds=int(data.get("desired_length_seconds", 30)),
            )
            plan = build_tiktok_plan(brief)
            output = {
                "topic": plan.topic,
                "hook": plan.hook,
                "hook_pattern": plan.hook_pattern,
                "caption": plan.caption,
                "keywords": list(plan.keywords),
                "hashtags": list(plan.hashtags),
                "cta": plan.cta,
                "quality_checks": list(plan.quality_checks),
                "provenance": list(plan.provenance),
            }
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.SUCCEEDED,
                output=output,
                started_at=started,
                completed_at=datetime.now(timezone.utc).isoformat(),
                metadata={"acquisition_mode": "extracted_and_reimplemented"},
            )
        except (TypeError, ValueError) as exc:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": type(exc).__name__, "message": str(exc), "failure_class": "validation"},
                started_at=started,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

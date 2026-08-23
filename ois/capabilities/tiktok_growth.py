from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from ois.kernel.contracts import AgentContract, InvocationRequest, InvocationResult
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel


@dataclass(frozen=True)
class TikTokContentBrief:
    topic: str
    audience: str = ""
    objective: str = "education"
    tone: str = "clear"


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


def _keywords(topic: str) -> tuple[str, ...]:
    words = [word.strip(".,!?;:#()[]{}") for word in topic.lower().split()]
    return tuple(dict.fromkeys(word for word in words if len(word) > 2))[:5]


def _select_pattern(brief: TikTokContentBrief) -> str:
    text = f"{brief.topic} {brief.objective}".lower()
    if any(token in text for token in ("mistake", "wrong", "avoid", "stop")):
        return "mistake_correction"
    if any(token in text for token in ("how", "steps", "guide", "tutorial")):
        return "step_by_step"
    if any(token in text for token in ("result", "increase", "reduce", "growth")):
        return "specific_outcome"
    return "problem_first"


def build_tiktok_plan(brief: TikTokContentBrief) -> TikTokContentPlan:
    """Create a deterministic OIS-native TikTok plan."""
    if not brief.topic.strip():
        raise ValueError("topic is required")

    pattern = _select_pattern(brief)
    keywords = _keywords(brief.topic)
    keyword_phrase = ", ".join(keywords) if keywords else brief.topic.strip()
    hook_templates = {
        "problem_first": f"If you are struggling with {brief.topic}, start here.",
        "mistake_correction": f"The biggest mistake with {brief.topic} is doing this first.",
        "specific_outcome": f"Here is a practical way to improve {brief.topic} without adding complexity.",
        "step_by_step": f"Here are the essential steps for {brief.topic}.",
    }
    hook = hook_templates[pattern]
    return TikTokContentPlan(
        topic=brief.topic,
        hook=hook,
        hook_pattern=pattern,
        caption=f"{hook} Focus: {keyword_phrase}. Test one change at a time.",
        keywords=keywords,
        hashtags=tuple(f"#{keyword}" for keyword in keywords[:3]),
        cta="Save this for later and comment with the result you want to improve.",
        quality_checks=(
            "single_clear_topic",
            "immediate_context",
            "caption_matches_hook",
            "keywords_are_natural",
            "hashtags_are_limited",
            "no_guaranteed_virality_claim",
        ),
    )


def _input_hash(data: Mapping[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TikTokContentAgent:
    """OIS agent that turns a content brief into a deterministic TikTok plan."""

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
                "tone": {"type": "string"},
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
        started = datetime.now(UTC).isoformat()
        try:
            data = request.input
            brief = TikTokContentBrief(
                topic=str(data.get("topic", "")),
                audience=str(data.get("audience", "")),
                objective=str(data.get("objective", "education")),
                tone=str(data.get("tone", "clear")),
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
            }
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.SUCCEEDED,
                output=output,
                started_at=started,
                completed_at=datetime.now(UTC).isoformat(),
                metadata={
                    "execution_provenance": {
                        "input_sha256": _input_hash(data),
                        "capability_version": self.contract.version,
                    }
                },
            )
        except (TypeError, ValueError) as exc:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": type(exc).__name__, "message": str(exc), "failure_class": "validation"},
                started_at=started,
                completed_at=datetime.now(UTC).isoformat(),
            )

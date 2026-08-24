from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ois.kernel.contracts import AgentContract, InvocationRequest, InvocationResult
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel
from ois.models import DeterministicTestProvider, LLMGateway, ModelRegistry, ModelRequest, ModelRoute


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


def build_tiktok_plan(brief: TikTokContentBrief, *, model_hook: str | None = None) -> TikTokContentPlan:
    """Create an OIS-native TikTok plan from the selected model output."""
    if not brief.topic.strip():
        raise ValueError("topic is required")

    pattern = _select_pattern(brief)
    keywords = _keywords(brief.topic)
    keyword_phrase = ", ".join(keywords) if keywords else brief.topic.strip()
    hook_templates = {
        "problem_first": f"If you are struggling with {brief.topic}, start here.",
        "mistake_correction": f"The biggest mistake with {brief.topic} is doing this first.",
        "specific_outcome": (
            f"Here is a practical way to improve {brief.topic} without adding complexity."
        ),
        "step_by_step": f"Here are the essential steps for {brief.topic}.",
    }
    hook = model_hook or hook_templates[pattern]
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


def _default_gateway() -> LLMGateway:
    registry = ModelRegistry()
    registry.register(
        ModelRoute(
            route_id="tiktok.deterministic.test.v1",
            provider_id=DeterministicTestProvider.provider_id,
            model_id="deterministic-tiktok-model",
            version="1.0.0",
            capabilities=frozenset({"text", "structured_output"}),
            max_input_classification="public",
            risk_levels=frozenset({"low"}),
            priority=10,
        ),
        DeterministicTestProvider(),
    )
    return LLMGateway(registry)


class TikTokContentAgent:
    """OIS agent that uses the canonical model/provider fabric."""

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
        model_requirements={
            "model_required": True,
            "required_capabilities": ["text", "structured_output"],
            "data_classification": "public",
        },
        max_iterations=1,
    )

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        self.gateway = gateway or _default_gateway()

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
            model_response = self.gateway.invoke(
                ModelRequest(
                    capability_id=self.contract.capability_id,
                    input=dict(data),
                    risk_level=self.contract.risk_level.value,
                    data_classification="public",
                    required_capabilities=frozenset({"text", "structured_output"}),
                )
            )
            plan = build_tiktok_plan(brief, model_hook=str(model_response.output["hook"]))
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
                        "model_route": model_response.route.route_id,
                        "model_id": model_response.route.model_id,
                        "model_version": model_response.route.version,
                        "provider_id": model_response.route.provider_id,
                        "model_usage": model_response.usage,
                    }
                },
            )
        except (KeyError, LookupError, TypeError, ValueError) as exc:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "failure_class": "model_routing" if isinstance(exc, LookupError) else "validation",
                },
                started_at=started,
                completed_at=datetime.now(UTC).isoformat(),
            )

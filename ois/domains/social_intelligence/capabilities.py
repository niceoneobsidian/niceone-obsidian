"""OIS Kernel capability bindings for the Social Intelligence Fabric."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel

from .fabric import InMemorySocialEventStore, build_signals, detect_trends, normalize_events
from .platforms import PlatformRegistry


class SocialIngestCapability:
    """Ingest normalized platform payloads into the canonical event store."""

    contract = CapabilityContract(
        capability_id="social.ingest",
        version="1.0.0",
        description="Normalize social source payloads into canonical SocialEvent records.",
        input_schema={"platform": "string", "payloads": "array"},
        output_schema={"events": "array", "persisted": "integer"},
        risk_level=RiskLevel.LOW,
        allowed_domains=("social_intelligence",),
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
    )

    def __init__(self, platforms: PlatformRegistry, store: InMemorySocialEventStore | None = None) -> None:
        self.platforms = platforms
        self.store = store or InMemorySocialEventStore()

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        platform = str(request.input.get("platform", ""))
        payloads = request.input.get("payloads", [])
        if not platform or not isinstance(payloads, list):
            raise ValueError("platform and payloads are required")
        self.platforms.get(platform)
        events = normalize_events(platform, payloads)
        persisted = sum(self.store.append(event) for event in events)
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"events": [event.__dict__ for event in events], "persisted": persisted},
        )


class SocialSignalCapability:
    """Derive deterministic, evidence-linked signals and trends from stored events."""

    contract = CapabilityContract(
        capability_id="social.signal_analysis",
        version="1.0.0",
        description="Analyze canonical social events into ranked signals and trends.",
        input_schema={"min_trend_count": "integer"},
        output_schema={"signals": "array", "trends": "array"},
        risk_level=RiskLevel.LOW,
        allowed_domains=("social_intelligence",),
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
    )

    def __init__(self, store: InMemorySocialEventStore) -> None:
        self.store = store

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        minimum = int(request.input.get("min_trend_count", 2))
        events = self.store.list()
        signals = build_signals(events)
        trends = detect_trends(events, min_count=minimum)
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={
                "signals": [signal.__dict__ for signal in signals],
                "trends": [trend.__dict__ for trend in trends],
                "event_count": len(events),
            },
        )


class SocialPublishCapability:
    """Governed publish boundary; real adapters must be explicitly registered."""

    contract = CapabilityContract(
        capability_id="social.publish",
        version="1.0.0",
        description="Publish content through an authorized platform adapter.",
        input_schema={"platform": "string", "content": "object"},
        output_schema={"publication": "object"},
        risk_level=RiskLevel.HIGH,
        permissions=("social.publish",),
        allowed_domains=("social_intelligence",),
        side_effects=SideEffectLevel.EXTERNAL,
        idempotent=False,
    )

    def __init__(self, platforms: PlatformRegistry) -> None:
        self.platforms = platforms

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        platform = str(request.input.get("platform", ""))
        content = request.input.get("content")
        if not platform or not isinstance(content, Mapping):
            raise ValueError("platform and content are required")
        result = self.platforms.get(platform).publish(content)
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"publication": dict(result)},
        )


def register_social_capabilities(registry: Any, platforms: PlatformRegistry, store: InMemorySocialEventStore | None = None) -> InMemorySocialEventStore:
    """Register the social capabilities in the supplied authoritative OIS registry."""
    event_store = store or InMemorySocialEventStore()
    registry.register(SocialIngestCapability(platforms, event_store))
    registry.register(SocialSignalCapability(event_store))
    registry.register(SocialPublishCapability(platforms))
    return event_store

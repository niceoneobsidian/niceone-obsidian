"""Bind Social Growth capabilities to the OIS Kernel execution contract.

The domain owns algorithms and connector adapters. The Kernel owns the
Capability contract, policy authorization, validation, checkpointing,
idempotency, recovery, and evidence lifecycle.
"""

from __future__ import annotations

from collections.abc import Sequence

from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel

from .connectors import ConnectorRegistry
from .evidence import SQLiteEvidenceLedger
from .intelligence import (
    build_audience_profiles,
    build_competitor_profiles,
    cluster_topics,
    detect_trends,
    extract_creative_patterns,
    resolve_entities,
    validate_events,
)
from .persistence import SocialEventStore, SQLiteSocialEventStore
from .schemas import SocialEvent, SocialResearchBrief, SocialSignal


class SocialIngestCapability:
    """Normalize and persist external payloads as canonical social events."""

    def __init__(
        self,
        connectors: ConnectorRegistry,
        *,
        event_store: SocialEventStore | None = None,
        evidence_ledger: SQLiteEvidenceLedger | None = None,
    ) -> None:
        self._connectors = connectors
        self._event_store = event_store or SQLiteSocialEventStore()
        self._evidence_ledger = evidence_ledger or SQLiteEvidenceLedger()
        self._contract = CapabilityContract(
            capability_id="social.ingest",
            version="1.0.0",
            description=(
                "Normalize and persist social platform payloads as canonical SocialEvent records."
            ),
            input_schema={"platform": "string", "payloads": "array"},
            output_schema={
                "events": "array",
                "persisted": "integer",
                "evidence_recorded": "integer",
            },
            risk_level=RiskLevel.LOW,
            allowed_domains=("social_growth",),
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
        )

    @property
    def contract(self) -> CapabilityContract:
        return self._contract

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        platform = str(request.input.get("platform", ""))
        payloads = request.input.get("payloads", [])
        if not isinstance(payloads, Sequence) or isinstance(payloads, str | bytes):
            raise TypeError("payloads must be a sequence")

        connector = self._connectors.get(platform)
        events = [connector.normalize_event(payload) for payload in payloads]
        persisted = sum(self._event_store.append(event) for event in events)
        evidence_recorded = sum(
            len(self._evidence_ledger.record_many(event.evidence)) for event in events
        )
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={
                "events": [event.model_dump(mode="json") for event in events],
                "persisted": persisted,
                "evidence_recorded": evidence_recorded,
            },
        )


class SocialResearchCapability:
    """Execute the deterministic Social Intelligence research pipeline."""

    def __init__(self) -> None:
        self._contract = CapabilityContract(
            capability_id="social.research.execute",
            version="1.0.0",
            description=(
                "Analyze canonical social events and produce an evidence-backed research brief."
            ),
            input_schema={"query": "string", "events": "array"},
            output_schema={"brief": "object"},
            risk_level=RiskLevel.LOW,
            allowed_domains=("social_growth",),
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
        )

    @property
    def contract(self) -> CapabilityContract:
        return self._contract

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        query = str(request.input.get("query", "")).strip()
        raw_events = request.input.get("events", [])
        if not query:
            raise ValueError("query is required")
        if not isinstance(raw_events, Sequence) or isinstance(raw_events, str | bytes):
            raise TypeError("events must be a sequence")

        events = [SocialEvent.model_validate(event) for event in raw_events]
        quality = validate_events(events)
        accepted = [
            event for event in events if event.platform and event.event_type and event.occurred_at
        ]

        entity_aliases = resolve_entities(accepted)
        topics = cluster_topics(accepted)
        trends = detect_trends(accepted)
        audiences = build_audience_profiles(accepted)
        competitors = build_competitor_profiles(accepted)
        creatives = extract_creative_patterns(accepted)

        signals: list[SocialSignal] = list(trends)
        for topic, _, count in topics:
            signals.append(
                SocialSignal(
                    signal_type="topic",
                    value=topic,
                    score=min(1.0, count / max(len(accepted), 1)),
                    confidence=0.6 if count > 1 else 0.4,
                )
            )

        sources = [evidence for event in accepted for evidence in event.evidence]
        findings = [
            f"Accepted {quality.accepted} social events and rejected {quality.rejected}.",
            f"Detected {len(topics)} lexical topic clusters.",
            f"Detected {len(trends)} trend signals.",
            f"Built {len(audiences)} audience profiles and {len(competitors)} competitor profiles.",
            f"Extracted {len(creatives)} creative hook patterns.",
        ]
        if quality.issues:
            findings.append(f"Data-quality warnings: {len(quality.issues)}.")

        brief = SocialResearchBrief(
            query=query,
            sources=sources,
            signals=signals,
            entities=sorted(entity for aliases in entity_aliases.values() for entity in aliases),
            findings=findings,
            confidence=min(1.0, 0.35 + 0.1 * len(signals) + 0.05 * len(sources)),
        )

        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={
                "brief": brief.model_dump(mode="json"),
                "quality": {
                    "accepted": quality.accepted,
                    "rejected": quality.rejected,
                    "issues": list(quality.issues),
                },
                "audiences": [profile.model_dump(mode="json") for profile in audiences],
                "competitors": [profile.model_dump(mode="json") for profile in competitors],
                "creative_patterns": [pattern.model_dump(mode="json") for pattern in creatives],
            },
        )


def register_social_kernel_capabilities(
    registry: CapabilityRegistry,
    *,
    connectors: ConnectorRegistry,
    event_store: SocialEventStore | None = None,
    evidence_ledger: SQLiteEvidenceLedger | None = None,
) -> None:
    """Register executable M13 capabilities in the authoritative Kernel registry."""
    registry.register(
        SocialIngestCapability(
            connectors,
            event_store=event_store,
            evidence_ledger=evidence_ledger,
        )
    )
    registry.register(SocialResearchCapability())

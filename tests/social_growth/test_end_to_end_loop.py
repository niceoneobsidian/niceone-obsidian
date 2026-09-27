from __future__ import annotations

from datetime import UTC, datetime

from ois.domains.social_growth.analytics_store import MetricObservation, SQLiteAnalyticsStore
from ois.domains.social_growth.attribution import AttributionTouchpoint, linear_attribution
from ois.domains.social_growth.attribution_store import SQLiteAttributionStore
from ois.domains.social_growth.connectors import ConnectorRegistry, GenericSocialConnector
from ois.domains.social_growth.experiments import (
    DeterministicExperimentExecutor,
    ExperimentRegistry,
)
from ois.domains.social_growth.kernel_integration import register_social_kernel_capabilities
from ois.domains.social_growth.memory import InMemoryMemoryAdapter, make_record
from ois.domains.social_growth.publish_capability import SocialPublishCapability
from ois.domains.social_growth.schemas import ExperimentSpec, PublishIntent
from ois.kernel.checkpoint import InMemoryCheckpointStore
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.policy import DefaultPolicyEngine
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import RiskLevel


def test_research_publish_measure_attribute_learn_loop() -> None:
    published: list[dict] = []
    connectors = ConnectorRegistry()
    connectors.register(
        GenericSocialConnector(
            "tiktok",
            publish_callable=lambda intent: published.append(intent.content) or {"id": "pub-1"},  # type: ignore
        )
    )

    registry = CapabilityRegistry()
    register_social_kernel_capabilities(registry, connectors=connectors)
    registry.register(SocialPublishCapability(connectors))
    policy = DefaultPolicyEngine(
        allowed_permissions=("social.publish",),
        maximum_risk=RiskLevel.HIGH,
        allow_irreversible=True,
    )
    checkpoints = InMemoryCheckpointStore()
    evidence = EvidenceLedger()
    runtime = ExecutionRuntime(registry, checkpoints, evidence, policy=policy)
    context = ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id="test-tenant", workflow_id="social.e2e", workflow_version="1.0"
        ),
        objective="research, publish and measure",
    )

    research = runtime.execute(
        context,
        "social.research.execute",
        "1.0.0",
        {
            "query": "AI content",
            "events": [
                {
                    "platform": "tiktok",
                    "event_type": "post",
                    "occurred_at": "2026-08-23T00:00:00+00:00",
                    "external_id": "p1",
                    "text": "AI content is accelerating",
                    "metrics": {"likes": 100, "comments": 10},
                }
            ],
        },
        invocation_id="e2e-research",
    )
    assert research.status.value == "succeeded"

    intent = PublishIntent(
        platform="tiktok",
        account_ref="test-account",
        content={"text": "AI content"},
    )
    context.approvals.append({"intent_id": intent.intent_id, "approved": True, "actor": "test"})
    publish = runtime.execute(
        context,
        "social.publish",
        "1.0.0",
        {"intent": intent.model_dump(mode="json")},
        invocation_id="e2e-publish",
    )
    assert publish.status.value == "succeeded"
    assert published == [{"text": "AI content"}]

    analytics = SQLiteAnalyticsStore()
    analytics.append(
        MetricObservation(
            observation_id="obs-1",
            entity_id="pub-1",
            metric="engagement",
            value=0.12,
            observed_at=datetime.now(UTC),
            platform="tiktok",
        )
    )
    assert analytics.latest("pub-1", "engagement") is not None

    attribution = linear_attribution(
        "conversion-1",
        [AttributionTouchpoint("pub-1", "campaign-1", "publish", datetime.now(UTC))],
        100.0,
    )
    attribution_store = SQLiteAttributionStore()
    assert attribution_store.append(attribution) == 1
    assert attribution_store.get("conversion-1") == [("pub-1", 100.0)]

    experiment = ExperimentSpec(
        experiment_id="exp-1",
        hypothesis="higher engagement",
        metric="engagement",
        control={"text": "A"},
        variants=[{"text": "B"}],
        success_threshold=0.1,
    )
    experiments = ExperimentRegistry()
    experiments.register(experiment)
    running = experiments.start("exp-1")
    assignment = DeterministicExperimentExecutor().assign(running, "audience-1")
    result = DeterministicExperimentExecutor().evaluate(running, assignment.variant_id, 0.12)
    assert result.accepted

    memory = InMemoryMemoryAdapter()
    memory.append(make_record("pattern:hook", "AI content", "creative_pattern", "e2e"))
    assert memory.search("AI content", kind="creative_pattern")

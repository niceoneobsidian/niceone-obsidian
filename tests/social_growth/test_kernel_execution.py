from __future__ import annotations

from datetime import UTC, datetime

from ois.domains.social_growth.connectors import ConnectorRegistry, GenericSocialConnector
from ois.domains.social_growth.kernel_integration import register_social_kernel_capabilities
from ois.kernel.checkpoint import InMemoryCheckpointStore
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity


def build_runtime() -> tuple[ExecutionRuntime, ExecutionContext, EvidenceLedger, InMemoryCheckpointStore]:
    connectors = ConnectorRegistry()
    connectors.register(GenericSocialConnector("tiktok"))

    registry = CapabilityRegistry()
    register_social_kernel_capabilities(registry, connectors=connectors)

    checkpoints = InMemoryCheckpointStore()
    evidence = EvidenceLedger()
    runtime = ExecutionRuntime(registry, checkpoints, evidence)
    context = ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id="test-tenant",
            workflow_id="social.research",
            workflow_version="1.0",
        ),
        objective="research social conversation",
    )
    return runtime, context, evidence, checkpoints


def test_social_ingest_executes_through_kernel() -> None:
    runtime, context, evidence, _ = build_runtime()

    result = runtime.execute(
        context,
        "social.ingest",
        "1.0.0",
        {
            "platform": "tiktok",
            "payloads": [
                {
                    "id": "post-1",
                    "event_type": "post",
                    "occurred_at": datetime(2026, 8, 23, tzinfo=UTC).isoformat(),
                    "text": "AI content strategy is moving fast",
                    "entities": ["Niceone Obsidian"],
                    "metrics": {"likes": 100, "comments": 10},
                }
            ],
        },
        invocation_id="test-execution:ingest",
    )

    assert result.status.value == "succeeded"
    assert result.output["events"][0]["platform"] == "tiktok"
    assert result.output["events"][0]["external_id"] == "post-1"
    assert evidence.count(context.identity.execution_id) >= 5


def test_social_research_executes_and_checkpoints() -> None:
    runtime, context, evidence, checkpoints = build_runtime()

    result = runtime.execute(
        context,
        "social.research.execute",
        "1.0.0",
        {
            "query": "AI content strategy",
            "events": [
                {
                    "platform": "tiktok",
                    "event_type": "post",
                    "occurred_at": "2026-08-23T00:00:00+00:00",
                    "external_id": "post-1",
                    "text": "AI content strategy is moving fast",
                    "entities": ["Competitor One"],
                    "metrics": {"likes": 100, "comments": 10},
                },
                {
                    "platform": "tiktok",
                    "event_type": "post",
                    "occurred_at": "2026-08-23T00:01:00+00:00",
                    "external_id": "post-2",
                    "text": "AI content strategy is becoming important",
                    "entities": ["Competitor One"],
                    "metrics": {"likes": 80, "comments": 8},
                },
            ],
        },
        invocation_id="test-execution:research",
    )

    assert result.status.value == "succeeded"
    assert result.output["brief"]["query"] == "AI content strategy"
    assert result.output["brief"]["entities"] == ["Competitor One"]
    assert result.output["quality"]["accepted"] == 2
    assert checkpoints.exists(context.identity.execution_id)
    assert any(event.event_type == "execution.authorized" for event in evidence.list(context.identity.execution_id))
    assert any(event.event_type == "capability.completed" for event in evidence.list(context.identity.execution_id))


def test_social_research_is_idempotent() -> None:
    runtime, context, evidence, _ = build_runtime()
    payload = {
        "query": "AI",
        "events": [
            {
                "platform": "tiktok",
                "event_type": "post",
                "occurred_at": "2026-08-23T00:00:00+00:00",
                "external_id": "post-1",
                "text": "AI is useful",
            }
        ],
    }

    first = runtime.execute(
        context,
        "social.research.execute",
        "1.0.0",
        payload,
        invocation_id="stable-research",
    )
    second = runtime.execute(
        context,
        "social.research.execute",
        "1.0.0",
        payload,
        invocation_id="stable-research",
    )

    assert first.output == second.output
    assert any(event.event_type == "execution.idempotency_hit" for event in evidence.list(context.identity.execution_id))

from uuid import uuid4

from ois.capabilities import register_tiktok_capabilities
from ois.kernel import (
    AgentRegistry,
    EvidenceLedger,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    InMemoryCheckpointStore,
    InvocationStatus,
    Supervisor,
)


def make_runtime():
    registry = AgentRegistry()
    agent = register_tiktok_capabilities(registry)
    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=EvidenceLedger(),
    )
    return registry, agent, runtime


def make_context() -> ExecutionContext:
    return ExecutionContext(
        identity=ExecutionIdentity(
            execution_id=uuid4(),
            tenant_id="ois-test",
        ),
        objective="Create a TikTok content plan",
    )


def test_tiktok_capability_is_registered():
    registry, agent, _ = make_runtime()
    assert agent.contract.capability_id == "tiktok.content.plan"
    assert registry.has("tiktok.content.plan", "1.0.0")


def test_tiktok_capability_executes_through_runtime_and_supervisor():
    _, _, runtime = make_runtime()
    result = Supervisor(runtime).execute(
        objective="Create a TikTok content plan",
        capability_id="tiktok.content.plan",
        version="1.0.0",
        input_data={
            "topic": "TikTok SEO mistakes",
            "audience": "creators",
            "objective": "education",
        },
        invocation_id="tiktok-integration-invocation-001",
        context=make_context(),
    )

    assert result.status == InvocationStatus.SUCCEEDED
    assert result.output["hook"]
    assert result.output["caption"]
    assert result.output["keywords"]
    assert result.output["hashtags"]
    assert result.output["cta"]
    assert "provenance" not in result.output
    assert result.metadata["execution_provenance"]["input_sha256"]


def test_tiktok_capability_is_idempotent_at_runtime_boundary():
    _, _, runtime = make_runtime()
    context = make_context()
    kwargs = dict(
        objective="Create a TikTok content plan",
        capability_id="tiktok.content.plan",
        version="1.0.0",
        input_data={"topic": "hook optimization"},
        invocation_id="tiktok-idempotency-001",
        context=context,
    )

    first = Supervisor(runtime).execute(**kwargs)
    second = Supervisor(runtime).execute(**kwargs)

    assert first.status == InvocationStatus.SUCCEEDED
    assert second.status == InvocationStatus.SUCCEEDED
    assert second.output == first.output

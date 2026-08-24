from ois.runtime.intelligence_fabrics import (
    ContextEngine,
    ContextRequest,
    KnowledgeEngine,
    LearningRuntime,
    MiddlewareContext,
    MiddlewarePipeline,
    MultimodalRuntime,
    ReasoningPattern,
    ReasoningRegistry,
    SocialIntelligenceRuntime,
    ToolRegistry,
)


def test_middleware_and_tools() -> None:
    seen: list[str] = []
    pipeline = MiddlewarePipeline([lambda ctx: (seen.append(ctx.phase), ctx)[1]])
    result = pipeline.before(MiddlewareContext("a", "s", "before_tool"))
    assert result.phase == "before_tool"
    assert seen == ["before_tool"]

    tools = ToolRegistry()
    tools.register("add", lambda a, b: a + b)
    assert tools.invoke("add", {"a": 2, "b": 3}) == 5


def test_context_and_knowledge() -> None:
    knowledge = KnowledgeEngine()
    knowledge.ingest("OIS social intelligence trend analysis", {"source": "test"})
    docs = knowledge.retrieve("trend analysis")
    context = ContextEngine().assemble(ContextRequest("research", knowledge=tuple({"role": "user", "content": d.content} for d in docs)))
    assert docs
    assert context.messages[0]["content"] == "research"


def test_reasoning_multimodal_social_and_learning() -> None:
    reasoning = ReasoningRegistry()
    reasoning.register(ReasoningPattern("reflection", ("research",), "iterative"))
    assert reasoning.select("research").name == "reflection"

    artifact = MultimodalRuntime().create("image", "s3://asset")
    assert artifact.media_type == "image"

    social = SocialIntelligenceRuntime()
    social.ingest("tiktok", "engagement", 0.9)
    assert len(social.query(platform="tiktok")) == 1

    learning = LearningRuntime()
    candidate = learning.propose("test hypothesis", ["evidence-1"])
    learning.mark_evaluated(candidate.candidate_id)
    assert learning.approve(candidate.candidate_id).status == "approved"

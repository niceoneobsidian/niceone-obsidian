from __future__ import annotations

from ois.capabilities.web_intelligence import (
    AdaptiveRouter,
    RuleBasedExtractor,
    RouteLearner,
    WebIntelligenceCapability,
    WebIntelligenceRequest,
    WebIntelligenceValidator,
)
from ois.capabilities.web_intelligence.models import SourceDocument


class FakeEngine:
    def __init__(self, name: str, body: str = "<html><body>Hello OIS</body></html>") -> None:
        self.name = name
        self.body = body
        self.calls = 0

    def can_handle(self, request: WebIntelligenceRequest) -> bool:
        return True

    def acquire(self, request: WebIntelligenceRequest) -> SourceDocument:
        self.calls += 1
        return SourceDocument(request.url, 200, "text/html", self.body, self.name)


def test_route_learner_prefers_successful_engine() -> None:
    learner = RouteLearner()
    learner.record("good", True)
    learner.record("bad", False)
    router = AdaptiveRouter([FakeEngine("bad"), FakeEngine("good")], learner)
    assert router.candidates(WebIntelligenceRequest("https://example.com"))[0].name == "good"


def test_capability_extracts_validates_and_records_provenance() -> None:
    engine = FakeEngine("fake")
    capability = WebIntelligenceCapability([engine], RuleBasedExtractor())
    result = capability.execute(WebIntelligenceRequest("https://example.com"))
    assert result.success is True
    assert result.engine == "fake"
    assert result.evidence is not None
    assert result.evidence["content_hash"]
    assert len(capability.provenance.records) == 1


def test_capability_falls_back_after_engine_failure() -> None:
    class Broken(FakeEngine):
        def acquire(self, request: WebIntelligenceRequest) -> SourceDocument:
            self.calls += 1
            raise RuntimeError("boom")

    broken = Broken("broken")
    good = FakeEngine("good")
    capability = WebIntelligenceCapability([broken, good], RuleBasedExtractor())
    result = capability.execute(WebIntelligenceRequest("https://example.com"))
    assert result.success is True
    assert result.engine == "good"
    assert result.attempts == 2


def test_http_route_is_rejected_for_javascript_requirement() -> None:
    from ois.capabilities.web_intelligence import HttpAcquisitionEngine

    engine = HttpAcquisitionEngine()
    assert engine.can_handle(WebIntelligenceRequest("https://example.com"))
    assert not engine.can_handle(
        WebIntelligenceRequest("https://example.com", javascript_required=True)
    )


def test_validator_rejects_empty_source() -> None:
    validator = WebIntelligenceValidator()
    source = SourceDocument("https://example.com", 200, "text/html", "", "fake")
    report = validator.validate_source(source, WebIntelligenceRequest("https://example.com"))
    assert report.valid is False
    assert "empty_source" in report.errors

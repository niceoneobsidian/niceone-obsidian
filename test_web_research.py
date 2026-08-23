from datetime import UTC, datetime

import pytest

from ois.capabilities.web_research import (
    ClaimStatus,
    SearchRequest,
    SearchResult,
    WebResearchService,
)


class FakeSearchProvider:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.requests: list[SearchRequest] = []

    def search(self, request: SearchRequest) -> list[SearchResult]:
        self.requests.append(request)
        return self.results


def result(snippet: str, source_type: str = "primary") -> SearchResult:
    return SearchResult(
        title="Example",
        url="https://example.com/source",
        snippet=snippet,
        published_at=datetime(2026, 8, 22, tzinfo=UTC),
        source_type=source_type,
    )


def test_request_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query"):
        SearchRequest(" ")


def test_request_rejects_invalid_result_limit() -> None:
    with pytest.raises(ValueError, match="max_results"):
        SearchRequest("test", max_results=0)


def test_result_requires_absolute_http_url() -> None:
    with pytest.raises(ValueError, match="HTTP\(S\)"):
        SearchResult("Example", "example.com", "text")


def test_research_is_deterministic_and_provider_agnostic() -> None:
    provider = FakeSearchProvider([result("OIS is governed by evidence.")])
    service = WebResearchService(provider)

    research = service.research(SearchRequest("OIS", max_results=1))

    assert research.status == "SUCCESS"
    assert len(research.results) == 1
    assert len(research.evidence) == 1
    assert research.evidence[0].confidence == 1.0
    assert provider.requests == [SearchRequest("OIS", max_results=1)]


def test_empty_provider_result_is_explicit() -> None:
    service = WebResearchService(FakeSearchProvider([]))

    research = service.research(SearchRequest("missing"))

    assert research.status == "EMPTY"
    assert research.results == ()
    assert research.evidence == ()


def test_claim_check_requires_evidence() -> None:
    provider = FakeSearchProvider([result("Evidence supports governed execution.")])
    evidence = WebResearchService(provider).research(SearchRequest("OIS")).evidence

    verified = WebResearchService.check_claim("Evidence supports governed execution.", evidence)
    unsupported = WebResearchService.check_claim("The system has autonomous publishing.", evidence)

    assert verified.status is ClaimStatus.VERIFIED
    assert verified.evidence_ids == ("E-001",)
    assert unsupported.status is ClaimStatus.UNSUPPORTED

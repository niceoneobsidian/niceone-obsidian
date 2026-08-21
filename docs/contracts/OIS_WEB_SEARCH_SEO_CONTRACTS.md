# OIS Web Search + SEO Capability Contracts

**Status:** DESIGNED / READY FOR CONTRACT + REGISTRY IMPLEMENTATION

## Capability: CAP-WEB-RESEARCH

### Input

```json
{
  "objective_id": "string",
  "topic": "string",
  "queries": ["string"],
  "freshness": "string|null",
  "language": "string|null",
  "region": "string|null",
  "max_results": 10,
  "citation_required": true
}
```

### Output

```json
{
  "research_id": "string",
  "results": [],
  "sources": [],
  "evidence": [],
  "status": "SUCCESS|PARTIAL|EMPTY|RATE_LIMITED|FAILED",
  "retrieved_at": "datetime"
}
```

## Capability: CAP-QUERY-GENERATION

Transforms a content objective into diversified research queries. Query types include primary, contextual, factual, trend, contradiction, and entity queries.

## Capability: CAP-SOURCE-EVALUATION

Ranks retrieved sources by authority, relevance, freshness, evidence directness, primary/secondary status, and duplication.

## Capability: CAP-EVIDENCE-EXTRACTION

Produces immutable evidence objects with claim, evidence text, source ID, timestamps, confidence, and provenance.

## Capability: CAP-RESEARCH-BRIEF

Compiles verified facts, trends, entities, questions, conflicts, uncertainties, and source mappings into a bounded generation context.

## Capability: CAP-CONTENT-SYNTHESIS

Generates original content from the research brief and creative objective. It must preserve factual qualifiers and cannot claim unsupported facts.

## Capability: CAP-FACT-CHECKING

Extracts factual claims and verifies each claim against the research evidence.

## Capability: CAP-CITATION-VALIDATION

Ensures every verified factual claim maps to one or more supporting sources and that the citation actually supports the claim.

## Capability: CAP-SEO-CONTENT-INTELLIGENCE

Adds SEO-specific context to the research brief: target terms, search intent, entities, topic gaps, questions, metadata, and structured-data requirements.

## Tool contracts

### SearchTool

```text
search(query, freshness, language, region, max_results, timeout) -> SearchResultSet
```

### SourceRetrieverTool

```text
retrieve(url, timeout) -> SourceDocument
```

### SourceParserTool

```text
parse(source_document) -> EvidenceCandidates
```

### ResearchCache

```text
get(normalized_query, freshness_window) -> CachedResearch | MISS
put(normalized_query, freshness_window, research) -> CacheReceipt
```

### CitationResolver

```text
resolve(claim, evidence_ids) -> CitationDecision
```

## Policy requirements

- Search tools require explicit capability authorization.
- Source retrieval must respect configured security/network policy.
- External content is untrusted input.
- Tool results cannot directly authorize publishing.
- Current/factual content with insufficient evidence must not be silently generated as fact.
- Publishing remains behind the OIS execution and approval boundary.

## Registry metadata

Each capability/tool registration must include identity, version, input/output schema, permissions, dependencies, risk, timeout/retry policy, validation requirements, evidence status, and activation state.
